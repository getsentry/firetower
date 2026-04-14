import logging
import re
from typing import Any

from firetower.auth.services import get_or_create_user_from_slack_id
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)

SLACK_USER_MENTION_RE = re.compile(r"<@(U[A-Z0-9]+)(?:\|[^>]*)?>")


def handle_captain_command(
    ack: Any, body: dict, command: dict, respond: Any, user_mention: str
) -> None:
    ack()
    channel_id = body.get("channel_id", "")
    incident = get_incident_from_channel(channel_id)
    if not incident:
        respond("Could not find an incident associated with this channel.")
        return

    match = SLACK_USER_MENTION_RE.search(user_mention)
    if not match:
        cmd = command.get("command", "/ft")
        respond(f"Usage: `{cmd} captain @user`")
        return

    slack_user_id = match.group(1)
    user = get_or_create_user_from_slack_id(slack_user_id)
    if not user:
        respond(f"Could not resolve <@{slack_user_id}> to a Firetower user.")
        return

    serializer = IncidentWriteSerializer(
        instance=incident, data={"captain": user.email}, partial=True
    )
    if serializer.is_valid():
        serializer.save()
        respond(
            f"{incident.incident_number} captain updated to {user.get_full_name()}."
        )
    else:
        respond(f"Failed to update captain: {serializer.errors}")
