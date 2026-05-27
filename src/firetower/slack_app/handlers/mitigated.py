import logging
from typing import Any

from django.conf import settings

from firetower.auth.services import get_or_create_user_from_slack_id
from firetower.incidents.models import Incident, IncidentStatus
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.slack_app.handlers.utils import (
    build_incident_lifecycle_modal,
    build_incident_update_data,
    get_incident_from_channel,
    parse_incident_form_values,
    validate_lifecycle_form,
)

logger = logging.getLogger(__name__)


def _build_mitigated_modal(incident: Incident, channel_id: str) -> dict:
    return build_incident_lifecycle_modal(
        incident=incident,
        channel_id=channel_id,
        title_text=incident.incident_number,
        callback_id="mitigated_incident_modal",
        intro_text="This incident is mitigated. Please confirm details below.",
    )


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
        view=_build_mitigated_modal(incident, channel_id),
    )


def handle_mitigated_submission(ack: Any, body: dict, view: dict, client: Any) -> None:
    form = parse_incident_form_values(view)
    channel_id = view.get("private_metadata", "")

    errors = validate_lifecycle_form(form)
    if errors:
        ack(response_action="errors", errors=errors)
        return

    ack()

    incident = get_incident_from_channel(channel_id)
    if not incident:
        logger.error("Mitigated submission: no incident for channel %s", channel_id)
        return

    captain_user = get_or_create_user_from_slack_id(form["captain_slack_id"])
    if not captain_user:
        logger.error(
            "Could not resolve Slack user %s to a Firetower user",
            form["captain_slack_id"],
        )
        client.chat_postMessage(
            channel=channel_id,
            text="Failed to resolve the selected captain to a Firetower user.",
        )
        return

    data = build_incident_update_data(
        form, IncidentStatus.MITIGATED, captain_user.email
    )

    serializer = IncidentWriteSerializer(instance=incident, data=data, partial=True)
    if not serializer.is_valid():
        logger.error("Mitigated update failed: %s", serializer.errors)
        client.chat_postMessage(
            channel=channel_id,
            text=f"Failed to update incident: {serializer.errors}",
        )
        return
    serializer.save()

    incident_url = f"{settings.FIRETOWER_BASE_URL}/{incident.incident_number}"
    client.chat_postMessage(
        channel=channel_id,
        text=(
            f"<{incident_url}|{incident.incident_number}> has been marked Mitigated.\n"
            f"Track follow-ups via the Action Items section on the incident page."
        ),
    )
