import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from django.conf import settings

from firetower.incidents.models import ExternalLink, ExternalLinkType
from firetower.integrations.services.notion import NotionService
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)


def handle_dumpslack_command(
    ack: Any,
    body: dict[str, Any],
    command: dict[str, Any],
    client: Any,
    respond: Any,
) -> None:
    ack()

    notion_config = settings.NOTION
    if not notion_config:
        respond("Notion integration is not configured.")
        return

    channel_id = body.get("channel_id", "")
    if not channel_id:
        respond("Could not determine the channel ID.")
        return

    incident = get_incident_from_channel(channel_id)
    if not incident:
        cmd = command.get("command", "/ft")
        respond(f"No incident found for this channel. Use `{cmd} new` to create one.")
        return

    notion = NotionService(
        integration_token=notion_config["INTEGRATION_TOKEN"],
        database_id=notion_config["DATABASE_ID"],
        template_id=notion_config.get("TEMPLATE_ID", ""),
    )

    existing_link = incident.external_links.filter(type=ExternalLinkType.NOTION).first()

    respond(
        "Fetching Slack history and generating postmortem doc, this may take a moment..."
    )

    if existing_link:
        page_id = _extract_notion_page_id(existing_link.url)
        if not page_id:
            respond("Could not parse existing Notion page ID from stored URL.")
            return
        page_url = existing_link.url
        messages = _get_channel_messages(client, channel_id)
    else:
        # Fetch template blocks and Slack messages in parallel before creating the page.
        with ThreadPoolExecutor(max_workers=2) as pool:
            messages_future = pool.submit(_get_channel_messages, client, channel_id)
            template_future = (
                pool.submit(notion.get_template_blocks) if notion.template_id else None
            )
            messages = messages_future.result()
            try:
                template_blocks, template_children = (
                    template_future.result() if template_future else ([], {})
                )
            except Exception:
                logger.exception("Failed to fetch Notion template blocks")
                template_blocks, template_children = [], {}

        base_url = settings.FIRETOWER_BASE_URL
        incident_url = f"{base_url}/{incident.incident_number}"
        captain_email = incident.captain.email if incident.captain else None

        try:
            page = notion.create_postmortem_page(
                incident_number=incident.incident_number,
                incident_title=incident.title,
                incident_url=incident_url,
                incident_date=incident.created_at,
                severity=incident.severity,
                captain_email=captain_email,
                template_blocks=template_blocks,
                template_children=template_children,
            )
        except Exception:
            logger.exception(
                "Failed to create Notion postmortem page for %s",
                incident.incident_number,
            )
            respond("Failed to create Notion postmortem page. Please try again.")
            return

        page_id = page["id"]
        page_url = page["url"]

        try:
            ExternalLink.objects.update_or_create(
                incident=incident,
                type=ExternalLinkType.NOTION,
                defaults={"url": page_url},
            )
        except Exception:
            logger.exception(
                "Failed to store Notion link on incident %s", incident.incident_number
            )

        try:
            client.bookmarks_add(
                channel_id=channel_id,
                title="Postmortem Doc",
                type="link",
                link=page_url,
            )
        except Exception:
            logger.exception("Failed to add Notion bookmark to channel %s", channel_id)

    action = "Created" if not existing_link else "Updated"

    try:
        notion.dump_slack_messages(page_id, messages)
    except Exception:
        logger.exception("Failed to dump Slack messages to Notion page %s", page_id)
        respond(
            f"Postmortem doc {action.lower()} but Slack dump failed. Check: {page_url}"
        )
        return

    respond(f"{action} postmortem doc: {page_url}")


def _build_user_email_cache(client: Any) -> dict[str, str]:
    """Batch-fetch all workspace users and return a slack_user_id -> email mapping.

    One users.list call (paginated) instead of one users_info call per unique
    author avoids N sequential API calls on channels with many participants.
    """
    cache: dict[str, str] = {}
    cursor: str | None = None

    while True:
        kwargs: dict[str, Any] = {"limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        try:
            response = client.users_list(**kwargs)
        except Exception:
            logger.exception("Failed to batch-fetch Slack users list")
            break
        if not response.get("ok"):
            logger.error("users_list returned not-ok")
            break
        for member in response.get("members", []):
            if member.get("deleted") or member.get("is_bot"):
                continue
            email = member.get("profile", {}).get("email", "")
            if email:
                cache[member["id"]] = email
        cursor = response.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break

    return cache


def _get_channel_messages(client: Any, channel_id: str) -> list[dict[str, Any]]:
    """Fetch up to 1000 channel messages with thread replies, excluding bots and system events."""
    try:
        response = client.conversations_history(channel=channel_id, limit=1000)
    except Exception:
        logger.exception("Failed to fetch history for channel %s", channel_id)
        return []

    if not response.get("ok"):
        logger.error("conversations_history returned not-ok for channel %s", channel_id)
        return []

    email_cache = _build_user_email_cache(client)

    def resolve_email(slack_user_id: str) -> str:
        if slack_user_id in email_cache:
            return email_cache[slack_user_id]
        # User not in the bulk list; fall back to individual lookup.
        try:
            info = client.users_info(user=slack_user_id)
            email = info["user"].get("profile", {}).get("email") or slack_user_id
            email_cache[slack_user_id] = email
            return email
        except Exception:
            return slack_user_id

    content: list[dict[str, Any]] = []
    for msg in response.get("messages", []):
        if msg.get("type") != "message":
            continue
        if not msg.get("user") or not msg.get("text"):
            continue
        if msg.get("bot_id") or msg.get("subtype") in ("channel_join", "channel_leave"):
            continue

        dt = datetime.fromtimestamp(float(msg["ts"]), tz=UTC)
        author = resolve_email(msg["user"])

        replies: list[dict[str, Any]] = []
        if msg.get("reply_count", 0) > 0:
            try:
                reply_resp = client.conversations_replies(
                    channel=channel_id, ts=msg["thread_ts"]
                )
                if reply_resp.get("ok"):
                    for reply in reply_resp.get("messages", []):
                        if reply.get("type") != "message" or reply["ts"] == msg["ts"]:
                            continue
                        if reply.get("bot_id"):
                            continue
                        replies.append(
                            {
                                "author": resolve_email(reply.get("user", "")),
                                "date_time": datetime.fromtimestamp(
                                    float(reply["ts"]), tz=UTC
                                ),
                                "text": reply.get("text", ""),
                            }
                        )
            except Exception:
                logger.exception("Failed to fetch replies for message %s", msg["ts"])

        content.append(
            {
                "author": author,
                "date_time": dt,
                "text": msg.get("text", ""),
                "replies": replies,
            }
        )

    content.reverse()  # chronological order
    return content


def _extract_notion_page_id(notion_url: str) -> str | None:
    """Extract UUID from a Notion page URL (with or without hyphens)."""
    match = re.search(
        r"([0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12})(?:\?|$)",
        notion_url.lower(),
    )
    if not match:
        return None
    raw = match.group(1).replace("-", "")
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
