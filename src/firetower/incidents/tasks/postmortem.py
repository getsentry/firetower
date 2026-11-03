import logging
from collections import defaultdict

from django.conf import settings

from firetower.incidents.hooks import get_postmortem_scheduler_bot_user_id
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentStatus,
)
from firetower.incidents.tasks.decorators import datadog_log
from firetower.integrations.services.slack import SlackService

logger = logging.getLogger(__name__)


def _prompt_scheduler_bot(
    incident_id: int,
    channel_id: str,
    message_ts: str,
    prompt_setting: str,
) -> None:
    """Mention the scheduler bot in the attendee prompt's thread with a configured prompt."""
    prompt = settings.SLACK.get(prompt_setting, "")
    bot_user_id = get_postmortem_scheduler_bot_user_id()
    if not prompt or not bot_user_id:
        return

    try:
        incident = Incident.objects.get(pk=incident_id)
    except Incident.DoesNotExist:
        logger.warning(f"Incident {incident_id} not found for {prompt_setting}")
        return

    if incident.is_private or incident.status not in (
        IncidentStatus.POSTMORTEM,
        IncidentStatus.DONE,
    ):
        return

    meeting_link = ExternalLink.objects.filter(
        incident=incident, type=ExternalLinkType.POSTMORTEM_MEETING_LINK
    ).first()

    slack = SlackService()
    text = f"<@{bot_user_id}> " + prompt.format_map(
        defaultdict(
            str,
            incident_number=incident.incident_number,
            prompt_url=slack.build_message_url(channel_id, message_ts),
            meeting_url=meeting_link.url if meeting_link else "",
        )
    )

    slack.invite_to_channel(channel_id, [bot_user_id])
    slack.post_message(channel_id, text, thread_ts=message_ts)


@datadog_log
def send_postmortem_attendee_followup(
    incident_id: int, channel_id: str, message_ts: str
) -> None:
    """Close the reaction window by posting the scheduler bot prompt for the reactors."""
    _prompt_scheduler_bot(
        incident_id, channel_id, message_ts, "POSTMORTEM_SCHEDULER_BOT_PROMPT"
    )


@datadog_log
def send_postmortem_final_call(
    incident_id: int, channel_id: str, message_ts: str
) -> None:
    """Ask the scheduler bot to invite late reactors the day before the meeting."""
    _prompt_scheduler_bot(
        incident_id, channel_id, message_ts, "POSTMORTEM_FINAL_CALL_PROMPT"
    )
