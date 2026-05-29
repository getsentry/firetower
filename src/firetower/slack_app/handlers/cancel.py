import logging
from typing import Any

from django.conf import settings

from firetower.incidents.models import IncidentStatus
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)


def _build_cancel_modal(channel_id: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "cancel_incident_modal",
        "private_metadata": channel_id,
        "title": {"type": "plain_text", "text": "Cancel incident"},
        "submit": {"type": "plain_text", "text": "Cancel incident"},
        "close": {"type": "plain_text", "text": "Back"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Cancel this incident. Please provide a reason.",
                },
            },
            {
                "type": "input",
                "block_id": "reason_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "reason",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Why is this incident being canceled?",
                    },
                },
                "label": {"type": "plain_text", "text": "Reason"},
            },
        ],
    }


def handle_cancel_command(ack: Any, body: dict, command: dict, respond: Any) -> None:
    ack()
    channel_id = body.get("channel_id", "")
    incident = get_incident_from_channel(channel_id)
    if not incident:
        respond("Could not find an incident associated with this channel.")
        return

    if incident.status == IncidentStatus.CANCELED:
        respond(f"{incident.incident_number} is already Canceled.")
        return

    trigger_id = body.get("trigger_id")
    if not trigger_id:
        respond("Could not open modal — missing trigger_id.")
        return

    from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415

    get_bolt_app().client.views_open(
        trigger_id=trigger_id,
        view=_build_cancel_modal(channel_id),
    )


def handle_cancel_submission(ack: Any, body: dict, view: dict, client: Any) -> None:
    values = view.get("state", {}).get("values", {})
    reason = values.get("reason_block", {}).get("reason", {}).get("value", "") or ""
    reason = reason.strip()

    if not reason:
        ack(
            response_action="errors",
            errors={"reason_block": "A reason is required."},
        )
        return

    ack()

    channel_id = view.get("private_metadata", "")
    incident = get_incident_from_channel(channel_id)
    if not incident:
        logger.error("Cancel submission: no incident for channel %s", channel_id)
        return

    serializer = IncidentWriteSerializer(
        instance=incident, data={"status": IncidentStatus.CANCELED}, partial=True
    )
    if not serializer.is_valid():
        logger.error("Cancel status update failed: %s", serializer.errors)
        client.chat_postMessage(
            channel=channel_id,
            text=f"Failed to cancel incident: {serializer.errors}",
        )
        return
    serializer.save()

    canceller_id = body.get("user", {}).get("id", "")
    incident_url = f"{settings.FIRETOWER_BASE_URL}/{incident.incident_number}"
    client.chat_postMessage(
        channel=channel_id,
        text=(
            f"<{incident_url}|{incident.incident_number}> has been Canceled "
            f"by <@{canceller_id}>.\n"
            f"*Reason*:\n"
            f"```{reason}```"
        ),
    )
