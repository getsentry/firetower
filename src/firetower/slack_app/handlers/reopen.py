import logging
from typing import Any

from firetower.incidents.models import IncidentStatus
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)


def handle_reopen_command(ack: Any, body: dict, command: dict, respond: Any) -> None:
    ack()
    channel_id = body.get("channel_id", "")
    actor_slack_id = body.get("user_id", "")
    incident = get_incident_from_channel(channel_id)
    if not incident:
        respond("Could not find an incident associated with this channel.")
        return

    if incident.status == IncidentStatus.ACTIVE:
        respond(f"{incident.incident_number} is already Active.")
        return

    serializer = IncidentWriteSerializer(
        instance=incident, data={"status": IncidentStatus.ACTIVE}, partial=True
    )
    if serializer.is_valid():
        serializer.save()
        respond(
            f"<@{actor_slack_id}> reopened {incident.incident_number}.",
            response_type="in_channel",
        )
    else:
        respond(f"Failed to reopen incident: {serializer.errors}")
