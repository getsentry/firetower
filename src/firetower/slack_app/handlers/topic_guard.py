import logging
from typing import Any

from firetower.incidents.hooks import _slack_service, build_channel_topic
from firetower.integrations.services.slack import escape_slack_text
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)

_bot_user_id: str | None = None


def _get_bot_user_id(client: Any) -> str | None:
    """Return the bot's own Slack user id, caching it after the first lookup."""
    global _bot_user_id  # noqa: PLW0603
    if _bot_user_id is None:
        _bot_user_id = client.auth_test()["user_id"]
    return _bot_user_id


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


def handle_channel_topic_change(event: dict, client: Any, logger: Any = logger) -> None:
    """Reset manual incident-channel topic edits and nudge the editor.

    Slack emits a ``channel_topic`` message event whenever a channel's topic
    changes, including when Firetower sets it. The bot-author guard prevents an
    infinite reset loop on our own edits.
    """
    if event.get("user") == _get_bot_user_id(client):
        return

    channel_id = event["channel"]
    incident = get_incident_from_channel(channel_id)
    if incident is None:
        return

    canonical = build_channel_topic(incident)
    attempted = event.get("topic", "")
    if attempted == canonical:
        return

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
