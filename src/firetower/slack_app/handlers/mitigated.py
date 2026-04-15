import logging
from typing import Any

from django.conf import settings

from firetower.incidents.models import IncidentStatus
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)


def _build_mitigated_modal(incident_number: str, channel_id: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "mitigated_incident_modal",
        "private_metadata": channel_id,
        "title": {"type": "plain_text", "text": incident_number},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Mark this incident as mitigated. Please provide the current impact and any remaining action items.",
                },
            },
            {
                "type": "input",
                "block_id": "impact_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "impact_update",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "What is the current impact after mitigation?",
                    },
                },
                "label": {
                    "type": "plain_text",
                    "text": "Current impact post-mitigation",
                },
            },
            {
                "type": "input",
                "block_id": "todo_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "todo_update",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "What still needs to be done?",
                    },
                },
                "label": {"type": "plain_text", "text": "Remaining action items"},
            },
        ],
    }


def handle_mitigated_command(ack: Any, body: dict, command: dict, respond: Any) -> None:
    ack()
    channel_id = body.get("channel_id", "")
    incident = get_incident_from_channel(channel_id)
    if not incident:
        respond("Could not find an incident associated with this channel.")
        return

    trigger_id = body.get("trigger_id")
    if not trigger_id:
        respond("Could not open modal — missing trigger_id.")
        return

    from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415

    get_bolt_app().client.views_open(
        trigger_id=trigger_id,
        view=_build_mitigated_modal(incident.incident_number, channel_id),
    )


def handle_mitigated_submission(ack: Any, body: dict, view: dict, client: Any) -> None:
    ack()
    values = view.get("state", {}).get("values", {})
    channel_id = view.get("private_metadata", "")

    impact = values.get("impact_block", {}).get("impact_update", {}).get("value", "")
    todo = values.get("todo_block", {}).get("todo_update", {}).get("value", "")

    incident = get_incident_from_channel(channel_id)
    if not incident:
        logger.error("Mitigated submission: no incident for channel %s", channel_id)
        return

    serializer = IncidentWriteSerializer(
        instance=incident, data={"status": IncidentStatus.MITIGATED}, partial=True
    )
    if not serializer.is_valid():
        logger.error("Mitigated status update failed: %s", serializer.errors)
        client.chat_postMessage(
            channel=channel_id,
            text=f"Failed to update incident status: {serializer.errors}",
        )
        return
    serializer.save()

    incident_url = f"{settings.FIRETOWER_BASE_URL}/{incident.incident_number}"
    client.chat_postMessage(
        channel=channel_id,
        text=(
            f"<{incident_url}|{incident.incident_number}> has been marked Mitigated.\n"
            f"*Current Impact*:\n"
            f"```{impact}```\n"
            f"*Remaining Action Items*:\n"
            f"```{todo}```"
        ),
    )
