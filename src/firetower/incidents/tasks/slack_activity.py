import logging
import time

from django.conf import settings
from django.utils import timezone

from firetower.incidents.hooks import HIGH_SEVERITIES
from firetower.incidents.models import (
    ExternalLinkType,
    Incident,
    IncidentStatus,
)
from firetower.incidents.tasks.decorators import datadog_log
from firetower.incidents.tasks.statuspage import _build_ic_mention
from firetower.integrations.services.slack import SlackService

logger = logging.getLogger(__name__)

DEFAULT_STALE_THRESHOLD_HIGH_SEVERITY_MINUTES = 120  # 2 hours for P0/P1
DEFAULT_STALE_THRESHOLD_LOW_SEVERITY_MINUTES = 1440  # 24 hours for P2+

STALE_ACTIVE_INCIDENT_REMINDER_MESSAGE = (
    ":wave: *Status Update Reminder*\n"
    "This incident has had no Slack activity for over {stale_duration}. "
    "If the incident has been mitigated or resolved, please update "
    "the status with `{slash_command} mitigated` or `{slash_command} resolved`."
    "{ic_mention}"
)

STALE_MITIGATED_INCIDENT_REMINDER_MESSAGE = (
    ":wave: *Status Update Reminder*\n"
    "This incident has been mitigated but has had no Slack activity "
    "for over {stale_duration}. "
    "If the incident has been fully resolved, please update "
    "the status with `{slash_command} resolved`."
    "{ic_mention}"
)

STALE_STATUSES = {IncidentStatus.ACTIVE, IncidentStatus.MITIGATED}


def _get_stale_threshold_minutes(incident: Incident) -> int:
    slack = settings.SLACK
    if incident.severity in HIGH_SEVERITIES:
        return slack.get(
            "STALE_THRESHOLD_HIGH_SEVERITY_MINUTES",
            DEFAULT_STALE_THRESHOLD_HIGH_SEVERITY_MINUTES,
        )
    return slack.get(
        "STALE_THRESHOLD_LOW_SEVERITY_MINUTES",
        DEFAULT_STALE_THRESHOLD_LOW_SEVERITY_MINUTES,
    )


def _format_duration(minutes: int) -> str:
    if minutes >= 60 and minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


@datadog_log
def send_stale_incident_reminder() -> None:
    incidents = Incident.objects.filter(status__in=STALE_STATUSES)
    if not incidents.exists():
        return

    slack = SlackService()
    slash_command = settings.SLACK.get("SLASH_COMMAND", "/inc")
    now = time.time()

    for incident in incidents:
        slack_link = incident.external_links.filter(type=ExternalLinkType.SLACK).first()
        if not slack_link:
            continue

        channel_id = slack.parse_channel_id_from_url(slack_link.url)
        if not channel_id:
            continue

        latest_ts = slack.get_latest_channel_activity_ts(channel_id)
        if latest_ts is None:
            # No human messages found in channel (empty or all bot messages)
            continue

        threshold_minutes = _get_stale_threshold_minutes(incident)
        threshold_seconds = threshold_minutes * 60
        if (now - latest_ts) < threshold_seconds:
            continue

        if incident.last_stale_reminder_sent_at is not None:
            last_sent = incident.last_stale_reminder_sent_at.timestamp()
            if last_sent > latest_ts:
                continue

        if incident.status == IncidentStatus.MITIGATED:
            template = STALE_MITIGATED_INCIDENT_REMINDER_MESSAGE
        else:
            template = STALE_ACTIVE_INCIDENT_REMINDER_MESSAGE

        stale_duration = _format_duration(threshold_minutes)
        logger.info(
            "Sending stale incident reminder for %s (%s, %s)",
            incident.incident_number,
            incident.status,
            incident.severity,
        )
        message = template.format(
            slash_command=slash_command,
            stale_duration=stale_duration,
            ic_mention=_build_ic_mention(incident),
        )
        slack.post_message(channel_id, message)
        incident.last_stale_reminder_sent_at = timezone.now()
        incident.save(update_fields=["last_stale_reminder_sent_at"])
