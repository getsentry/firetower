import logging
from collections import defaultdict

from django.conf import settings

from firetower.incidents.models import Incident, IncidentStatus
from firetower.incidents.tasks.decorators import datadog_log
from firetower.integrations.services.slack import SlackService

logger = logging.getLogger(__name__)


@datadog_log
def send_postmortem_attendee_followup(
    incident_id: int, channel_id: str, message_ts: str
) -> None:
    """Close the reaction window by posting the scheduler bot prompt for the reactors."""
    prompt = settings.SLACK.get("POSTMORTEM_SCHEDULER_BOT_PROMPT", "")
    if not prompt:
        return

    try:
        incident = Incident.objects.get(pk=incident_id)
    except Incident.DoesNotExist:
        logger.warning(
            f"Incident {incident_id} not found for postmortem attendee followup"
        )
        return

    if incident.status not in (IncidentStatus.POSTMORTEM, IncidentStatus.DONE):
        return

    slack = SlackService()
    text = prompt.format_map(
        defaultdict(
            str,
            incident_number=incident.incident_number,
            prompt_url=slack.build_message_url(channel_id, message_ts),
        )
    )

    bot_user_id = settings.SLACK.get("POSTMORTEM_SCHEDULER_BOT_USER_ID", "")
    if bot_user_id:
        slack.invite_to_channel(channel_id, [bot_user_id])
        text = f"<@{bot_user_id}> {text}"

    slack.post_message(channel_id, text)
