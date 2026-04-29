import logging
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import requests
import sentry_sdk
from django.conf import settings
from django.db import transaction

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.models import ExternalLink, ExternalLinkType
from firetower.integrations.services.notion import NotionService
from firetower.integrations.services.slack import SlackService
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)


def _get_notion_config() -> dict | None:
    config = settings.NOTION
    if (
        not config
        or config.get("INTEGRATION_TOKEN", "") == ""
        or config.get("DATABASE_ID", "") == ""
    ):
        return None
    return config


def _trigger_slack_dump(client: Any, channel_id: str, incident: Any) -> None:
    notion_config = _get_notion_config()
    if not notion_config:
        return

    notion = NotionService(
        integration_token=notion_config["INTEGRATION_TOKEN"],
        database_id=notion_config["DATABASE_ID"],
        template_markdown=notion_config.get("TEMPLATE_MARKDOWN", ""),
    )

    page_id: str | None = None
    page_url: str = ""
    update_slack: bool = False
    created: bool = False

    try:
        with transaction.atomic():
            notion_link, created = (
                ExternalLink.objects.select_for_update().get_or_create(
                    incident=incident,
                    type=ExternalLinkType.NOTION,
                    defaults={"url": ""},
                )
            )
            if not created and notion_link.url:
                page_id = _extract_notion_page_id(notion_link.url)
                if not page_id:
                    try:
                        client.chat_postMessage(
                            channel=channel_id,
                            text="Could not parse existing Notion page ID from stored URL.",
                        )
                    except Exception:
                        logger.exception(
                            "Failed to post Notion page ID error to channel %s",
                            channel_id,
                        )
                    return
                page_url = notion_link.url
                update_slack = True
            else:
                base_url = settings.FIRETOWER_BASE_URL
                incident_url = f"{base_url}/{incident.incident_number}"
                captain_email = incident.captain.email if incident.captain else None
                page = notion.create_postmortem_page(
                    incident_number=incident.incident_number,
                    incident_title=incident.title,
                    incident_url=incident_url,
                    incident_date=incident.created_at,
                    severity=incident.severity,
                    captain_email=captain_email,
                )
                page_id = page["id"]
                page_url = page["url"]
                notion_link.url = page_url
                notion_link.save(update_fields=["url"])
    except Exception:
        logger.exception(
            "Failed to create Notion postmortem page for %s",
            incident.incident_number,
        )
        try:
            client.chat_postMessage(
                channel=channel_id,
                text="Failed to create Notion postmortem page. Please try again.",
            )
        except Exception:
            logger.exception(
                "Failed to post Notion creation error to channel %s", channel_id
            )
        return

    action = "Created" if created else "Updated"

    slack_service = SlackService()
    messages = _get_channel_messages(slack_service, channel_id)

    try:
        notion.apply_template(page_id, messages, update_slack=update_slack)
    except Exception:
        logger.exception("Failed to populate Notion page %s", page_id)
        try:
            client.chat_postMessage(
                channel=channel_id,
                text=f"Postmortem doc {action.lower()} but content dump failed. Check: {page_url}",
            )
        except Exception:
            logger.exception(
                "Failed to post template failure message to channel %s", channel_id
            )
        return

    if created:
        try:
            client.bookmarks_add(
                channel_id=channel_id,
                title="Postmortem Doc",
                type="link",
                link=page_url,
            )
        except Exception:
            logger.exception("Failed to add Notion bookmark to channel %s", channel_id)

    try:
        client.chat_postMessage(
            channel=channel_id, text=f"{action} postmortem doc: {page_url}"
        )
    except Exception:
        logger.exception(
            "Failed to post completion message to channel %s for page %s",
            channel_id,
            page_url,
        )


def handle_dumpslack_command(
    ack: Any,
    body: dict[str, Any],
    command: dict[str, Any],
    client: Any,
    respond: Any,
) -> None:
    ack()

    if not _get_notion_config():
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

    respond(
        "Fetching Slack history and generating postmortem doc, this may take a moment..."
    )
    _trigger_slack_dump(client, channel_id, incident)


def _resolve_user_emails(
    service: SlackService, slack_user_ids: set[str]
) -> dict[str, str]:
    profiles = ExternalProfile.objects.filter(
        type=ExternalProfileType.SLACK,
        external_id__in=slack_user_ids,
    ).select_related("user")
    cache: dict[str, str] = {p.external_id: p.user.email for p in profiles}

    for slack_id in slack_user_ids - cache.keys():
        user_info = service.get_user_info(slack_id)
        cache[slack_id] = (user_info or {}).get("email") or slack_id

    return cache


def _get_channel_messages(
    service: SlackService, channel_id: str
) -> list[dict[str, Any]]:
    all_messages = service.get_channel_history(channel_id)

    if not all_messages:
        return []

    filtered: list[dict[str, Any]] = []
    for msg in all_messages:
        if msg.get("type") != "message":
            continue
        if not msg.get("user"):
            continue
        if msg.get("bot_id") or msg.get("subtype") in ("channel_join", "channel_leave"):
            continue
        if not msg.get("text") and not _extract_image_urls(msg):
            continue
        filtered.append(msg)

    all_raw_replies: dict[str, list[dict[str, Any]]] = {}
    for msg in filtered:
        if msg.get("reply_count", 0) > 0:
            all_raw_replies[msg["thread_ts"]] = service.get_thread_replies(
                channel_id, msg["thread_ts"]
            )

    slack_user_ids: set[str] = set()
    for msg in filtered:
        slack_user_ids.add(msg["user"])
    for replies in all_raw_replies.values():
        for reply in replies:
            if reply.get("user"):
                slack_user_ids.add(reply["user"])

    email_cache = _resolve_user_emails(service, slack_user_ids)

    content: list[dict[str, Any]] = []
    for msg in filtered:
        image_urls = _extract_image_urls(msg)
        dt = datetime.fromtimestamp(float(msg["ts"]), tz=UTC)
        author = email_cache.get(msg["user"], msg["user"])

        raw_replies = all_raw_replies.get(msg.get("thread_ts"), [])
        replies: list[dict[str, Any]] = [
            {
                "author": email_cache.get(reply.get("user", ""), reply.get("user", "")),
                "date_time": datetime.fromtimestamp(float(reply["ts"]), tz=UTC),
                "text": reply.get("text", ""),
            }
            for reply in raw_replies
        ]

        images = []
        for item in image_urls:
            result = _download_image(item["image_url"], service.bot_token or "")
            if result:
                data, content_type = result
                images.append(
                    {
                        "data": data,
                        "content_type": content_type,
                        "image_url": item["image_url"],
                        "source_url": item["source_url"],
                    }
                )
            else:
                logger.warning(
                    "Failed to download image %s for channel %s",
                    item["image_url"],
                    channel_id,
                )

        content.append(
            {
                "author": author,
                "date_time": dt,
                "text": msg.get("text", ""),
                "replies": replies,
                "images": images,
            }
        )

    content.reverse()
    return content


def _extract_image_urls(msg: dict[str, Any]) -> list[dict[str, str]]:
    items = []
    for attachment in msg.get("attachments", []):
        image_url = attachment.get("image_url")
        if image_url:
            source_url = (
                attachment.get("title_link")
                or attachment.get("from_url")
                or attachment.get("original_url")
                or ""
            )
            items.append({"image_url": image_url, "source_url": source_url})
    for file_info in msg.get("files", []):
        if file_info.get("mimetype", "").startswith("image/"):
            url = file_info.get("url_private") or file_info.get(
                "url_private_download", ""
            )
            if url:
                items.append({"image_url": url, "source_url": ""})
    for block in msg.get("blocks", []):
        if block.get("type") == "image":
            image_url = block.get("image_url", "")
            if image_url:
                items.append({"image_url": image_url, "source_url": ""})
        accessory = block.get("accessory") or {}
        if accessory.get("type") == "image":
            image_url = accessory.get("image_url", "")
            if image_url:
                items.append({"image_url": image_url, "source_url": ""})
        for element in block.get("elements", []):
            if isinstance(element, dict) and element.get("type") == "image":
                image_url = element.get("image_url", "")
                if image_url:
                    items.append({"image_url": image_url, "source_url": ""})
    return items


def _is_slack_url(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
        return host == "slack.com" or host.endswith(".slack.com")
    except Exception:
        return False


def _download_image(url: str, slack_token: str) -> tuple[bytes, str] | None:
    headers: dict[str, str] = {}
    if _is_slack_url(url):
        headers["Authorization"] = f"Bearer {slack_token}"
    try:
        resp = requests.get(url, headers=headers, timeout=30.0)
        resp.raise_for_status()
        content_type = (
            resp.headers.get("content-type", "image/png").split(";")[0].strip()
        )
        if not content_type.startswith("image/"):
            logger.warning(
                "URL %s returned non-image content-type %s", url, content_type
            )
            return None
        return resp.content, content_type
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.exception("Failed to download image from %s", url)
        return None


def _extract_notion_page_id(notion_url: str) -> str | None:
    match = re.search(
        r"([0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12})(?:[/?]|$)",
        notion_url.lower(),
    )
    if not match:
        return None
    raw = match.group(1).replace("-", "")
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
