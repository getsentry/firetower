import logging
import threading
from collections import OrderedDict
from typing import Any

from firetower.incidents.hooks import build_channel_topic
from firetower.integrations.services.slack import SlackService, escape_slack_text
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)

_slack_service = SlackService()

_bot_user_id: str | None = None

# Bounded set of recently handled channel_topic event ids, used to drop Slack
# redeliveries. Socket Mode strips the X-Slack-Retry-Num header (it lives on the
# envelope, not the event payload Bolt forwards), so we dedup on the event's own
# id/timestamp instead.
_RECENT_EVENT_CACHE_SIZE = 256
_recent_event_ids: "OrderedDict[str, None]" = OrderedDict()
# Bolt dispatches event listeners on a thread pool, so guard the cache against
# concurrent check-then-set/evict races.
_recent_event_ids_lock = threading.Lock()


def _get_bot_user_id(client: Any) -> str | None:
    """Return the bot's own Slack user id, caching it after the first lookup."""
    global _bot_user_id  # noqa: PLW0603
    if _bot_user_id is None:
        try:
            _bot_user_id = client.auth_test()["user_id"]
        except Exception:
            logger.exception("auth_test failed while resolving bot user id")
            return None
    return _bot_user_id


def _event_id(event: dict) -> str | None:
    return event.get("event_ts") or event.get("ts")


def _seen_recently(event_id: str) -> bool:
    """Return True if this event id was already handled, recording it otherwise."""
    with _recent_event_ids_lock:
        if event_id in _recent_event_ids:
            return True
        _recent_event_ids[event_id] = None
        while len(_recent_event_ids) > _RECENT_EVENT_CACHE_SIZE:
            _recent_event_ids.popitem(last=False)
        return False


def _is_slack_retry(request: Any) -> bool:
    """Best-effort detection of a Slack event redelivery.

    Works in HTTP mode where Bolt exposes the X-Slack-Retry-Num header. Under
    Socket Mode (how Firetower runs) the header is absent, so callers must also
    rely on the event-id dedup cache.
    """
    if request is None:
        return False
    headers = getattr(request, "headers", None)
    if not headers:
        return False
    value = headers.get("x-slack-retry-num")
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    return bool(value)


def _build_reset_message(attempted: str) -> str:
    lines = [
        "Channel topics here are managed by Firetower and reflect the incident's "
        "current status, so I reset it.",
    ]
    if attempted:
        quoted = "\n".join(
            f"> {escape_slack_text(line)}" for line in attempted.splitlines()
        )
        lines.append(f"You tried to set:\n{quoted}")
    lines.append(
        "To change incident details (which update the topic automatically), use "
        "`/ft subject <title>`, `/ft severity <P0-P4>`, or `/ft captain @user`."
    )
    return "\n\n".join(lines)


def handle_channel_topic_change(event: dict, client: Any, request: Any = None) -> None:
    """Reset manual incident-channel topic edits and nudge the editor.

    Slack emits a ``channel_topic`` message event whenever a channel's topic
    changes, including when Firetower sets it. The bot-author guard prevents an
    infinite reset loop on our own edits, and a retry/dedup guard prevents a
    second reset and ephemeral when Slack redelivers the event.
    """
    if event.get("user") == _get_bot_user_id(client):
        return

    channel_id = event.get("channel")
    if not channel_id:
        return

    event_id = _event_id(event)
    if _is_slack_retry(request) or (event_id is not None and _seen_recently(event_id)):
        logger.info("Skipping duplicate channel_topic event for channel %s", channel_id)
        return

    incident = get_incident_from_channel(channel_id)
    if incident is None:
        return

    canonical = build_channel_topic(incident)
    attempted = event.get("topic", "")

    logger.info(
        "Resetting manual topic change in incident channel %s (incident %s)",
        channel_id,
        incident.incident_number,
    )
    _slack_service.set_channel_topic(channel_id, canonical)

    try:
        client.chat_postEphemeral(
            channel=channel_id,
            user=event.get("user"),
            text=_build_reset_message(attempted),
        )
    except Exception:
        logger.exception("Failed to post topic-reset ephemeral to %s", channel_id)
