import logging
import re

from firetower.incidents.hooks import (
    get_postmortem_scheduler_bot_user_id,
    record_postmortem_meeting,
)
from firetower.incidents.models import IncidentStatus
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)

MEET_URL_PATTERN = re.compile(r"https://meet\.google\.com/[a-z]+-[a-z]+-[a-z]+")


def is_postmortem_meeting_message(event: dict) -> bool:
    """Match scheduler bot messages that contain a Google Meet link."""
    bot_user_id = get_postmortem_scheduler_bot_user_id()
    return (
        bool(bot_user_id)
        and event.get("user") == bot_user_id
        and MEET_URL_PATTERN.search(event.get("text", "")) is not None
    )


def handle_postmortem_meeting_message(event: dict) -> None:
    """Record the meeting link the scheduler bot posted for a postmortem incident."""
    match = MEET_URL_PATTERN.search(event.get("text", ""))
    channel_id = event.get("channel")
    if not match or not channel_id:
        return

    incident = get_incident_from_channel(channel_id)
    if incident is None or incident.status not in (
        IncidentStatus.POSTMORTEM,
        IncidentStatus.DONE,
    ):
        return

    logger.info(
        "Recording postmortem meeting link for incident %s", incident.incident_number
    )
    record_postmortem_meeting(incident, match.group(0))
