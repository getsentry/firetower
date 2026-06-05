import logging
from typing import Any

from firetower.auth.services import get_or_create_user_from_slack_id
from firetower.incidents.models import IncidentSeverity
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)

VALID_SEVERITIES = {s.value.lower(): s.value for s in IncidentSeverity}


def handle_severity_command(
    ack: Any, body: dict, command: dict, respond: Any, new_severity: str
) -> None:
    ack()
    channel_id = body.get("channel_id", "")
    incident = get_incident_from_channel(channel_id)
    if not incident:
        respond("Could not find an incident associated with this channel.")
        return

    normalized = VALID_SEVERITIES.get(new_severity.lower())
    if not normalized:
        valid = ", ".join(VALID_SEVERITIES.values())
        respond(f"Invalid severity `{new_severity}`. Must be one of: {valid}")
        return

    acting_user = get_or_create_user_from_slack_id(body.get("user_id", ""))
    serializer = IncidentWriteSerializer(
        instance=incident,
        data={"severity": normalized},
        partial=True,
        context={"acting_user": acting_user},
    )
    if serializer.is_valid():
        serializer.save()
        respond(f"{incident.incident_number} severity updated to {normalized}.")
    else:
        respond(f"Failed to update severity: {serializer.errors}")

    # TODO: P0/P1 upgrade handling (PagerDuty, status channel) will be added in RELENG-465
