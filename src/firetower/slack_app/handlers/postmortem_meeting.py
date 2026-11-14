import logging
import re
from datetime import datetime

from firetower.incidents.hooks import (
    get_postmortem_scheduler_bot_user_id,
    record_postmortem_meeting,
    schedule_postmortem_final_call,
)
from firetower.incidents.models import IncidentStatus
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)

MEET_URL_PATTERN = re.compile(r"https://meet\.google\.com/[a-z]+-[a-z]+-[a-z]+")
MEETING_START_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})"
)


def is_postmortem_meeting_message(event: dict) -> bool:
    """Match scheduler bot messages that contain a Google Meet link."""
    bot_user_id = get_postmortem_scheduler_bot_user_id()
    return (
        bool(bot_user_id)
        and event.get("user") == bot_user_id
        and MEET_URL_PATTERN.search(event.get("text", "")) is not None
    )


def parse_meeting_start(text: str) -> datetime | None:
    """Return the first timezone-aware ISO 8601 timestamp in the text, if any."""
    match = MEETING_START_PATTERN.search(text)
    if not match:
        return None
    try:
        return datetime.fromisoformat(match.group(0))
    except ValueError:
        return None


def handle_postmortem_meeting_message(event: dict) -> None:
    """Record the meeting link the scheduler bot posted for a postmortem incident."""
    text = event.get("text", "")
    match = MEET_URL_PATTERN.search(text)
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

    thread_ts = event.get("thread_ts")
    meeting_start = parse_meeting_start(text)
    if thread_ts and meeting_start:
        schedule_postmortem_final_call(incident, channel_id, thread_ts, meeting_start)
