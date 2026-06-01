import logging
from typing import Any

from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)


def handle_subject_command(
    ack: Any, body: dict, command: dict, respond: Any, new_subject: str
) -> None:
    ack()
    channel_id = body.get("channel_id", "")
    actor_slack_id = body.get("user_id", "")
    incident = get_incident_from_channel(channel_id)
    if not incident:
        respond("Could not find an incident associated with this channel.")
        return

    serializer = IncidentWriteSerializer(
        instance=incident, data={"title": new_subject}, partial=True
    )
    if serializer.is_valid():
        serializer.save()
        respond(
            f"<@{actor_slack_id}> updated {incident.incident_number} subject to: {new_subject}",
            response_type="in_channel",
        )
    else:
        respond(f"Failed to update subject: {serializer.errors}")
