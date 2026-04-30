import logging
import re
import threading
from datetime import UTC, datetime
from typing import Any

import requests
import sentry_sdk
from django.conf import settings
from django.db import transaction

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.models import ExternalLink, ExternalLinkType
from firetower.integrations.services.genai import GenAIService
from firetower.integrations.services.notion import NotionService
from firetower.integrations.services.slack import SlackService, is_slack_url
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)


def _trigger_slack_dump(client: Any, channel_id: str, incident: Any) -> None:
    notion = NotionService.from_settings()
    if not notion:
        return

    page_id: str | None = None
    page_url: str = ""
    update_slack: bool = False
    notion_page_created: bool = False

    try:
        with transaction.atomic():
            notion_link, db_record_created = (
                ExternalLink.objects.select_for_update().get_or_create(
                    incident=incident,
                    type=ExternalLinkType.NOTION,
                    defaults={"url": ""},
                )
            )
            existing_url = notion_link.url

        # Notion API calls happen outside the transaction to avoid holding the
        # SELECT FOR UPDATE lock while making slow external requests.
        if not db_record_created and existing_url:
            page_id = _extract_notion_page_id(existing_url)
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
            page_url = existing_url
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
            # Re-acquire lock before saving to detect concurrent callers that
            # also saw url="" and raced to create a page. The loser exits here;
            # the winner's URL and apply_template call stand.
            with transaction.atomic():
                notion_link = ExternalLink.objects.select_for_update().get(
                    incident=incident,
                    type=ExternalLinkType.NOTION,
                )
                if notion_link.url:
                    logger.warning(
                        "Race condition: concurrent call already created Notion page for %s",
                        incident.incident_number,
                    )
                    return
                notion_link.url = page_url
                notion_link.save(update_fields=["url"])
            notion_page_created = True
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

    action = "Created" if notion_page_created else "Updated"

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

    try:
        genai = GenAIService.from_settings()
        if genai:
            timeline = genai.generate_timeline(messages, incident_summary=incident.title)
            if timeline:
                notion.add_timeline_to_page(page_id, timeline)
    except Exception:
        logger.exception("Failed to add AI timeline to Notion page %s", page_id)

    if notion_page_created:
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


def trigger_slack_dump_async(client: Any, channel_id: str, incident: Any) -> None:
    def _run() -> None:
        from django.db import connection  # noqa: PLC0415

        try:
            _trigger_slack_dump(client, channel_id, incident)
        finally:
            connection.close()

    threading.Thread(target=_run, daemon=True).start()


def handle_dumpslack_command(
    ack: Any,
    body: dict[str, Any],
    command: dict[str, Any],
    client: Any,
    respond: Any,
) -> None:
    ack()

    if not NotionService.is_configured():
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
    trigger_slack_dump_async(client, channel_id, incident)


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
    filtered_image_urls: dict[str, list[dict[str, str]]] = {}
    for msg in all_messages:
        if msg.get("type") != "message":
            continue
        if not msg.get("ts"):
            continue
        if not msg.get("user"):
            continue
        if msg.get("bot_id") or msg.get("subtype") in (
            "channel_join",
            "channel_leave",
            "thread_broadcast",
        ):
            continue
        image_urls = _extract_image_urls(msg)
        if not msg.get("text") and not image_urls:
            continue
        filtered.append(msg)
        filtered_image_urls[msg["ts"]] = image_urls

    all_raw_replies: dict[str, list[dict[str, Any]]] = {}
    for msg in filtered:
        if msg.get("reply_count", 0) > 0:
            all_raw_replies[msg["ts"]] = service.get_thread_replies(
                channel_id, msg["ts"]
            )

    slack_user_ids: set[str] = set()
    for msg in filtered:
        slack_user_ids.add(msg["user"])
    for thread_replies in all_raw_replies.values():
        for reply in thread_replies:
            if reply.get("user"):
                slack_user_ids.add(reply["user"])

    email_cache = _resolve_user_emails(service, slack_user_ids)

    content: list[dict[str, Any]] = []
    for msg in filtered:
        image_urls = filtered_image_urls[msg["ts"]]
        dt = datetime.fromtimestamp(float(msg["ts"]), tz=UTC)
        author = email_cache.get(msg["user"], msg["user"])

        raw_replies = all_raw_replies.get(msg["ts"], [])
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


def _download_image(url: str, slack_token: str) -> tuple[bytes, str] | None:
    headers: dict[str, str] = {}
    if is_slack_url(url):
        headers["Authorization"] = f"Bearer {slack_token}"
    try:
        session = requests.Session()
        if slack_token and is_slack_url(url):
            # requests strips Authorization on redirect by default; re-add it for
            # Slack-to-Slack redirects so files-pri URLs don't land on an HTML login page.
            def _rebuild_auth(prepared_request: Any, response: Any) -> None:
                if is_slack_url(prepared_request.url):
                    prepared_request.headers["Authorization"] = f"Bearer {slack_token}"
                else:
                    prepared_request.headers.pop("Authorization", None)

            session.rebuild_auth = _rebuild_auth  # type: ignore[method-assign]
        resp = session.get(url, headers=headers, timeout=30.0)
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
