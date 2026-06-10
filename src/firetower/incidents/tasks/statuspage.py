import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from firetower.incidents.hooks import (
    ACTIVE_STATUSES,
    HIGH_SEVERITIES,
    get_slack_user_id,
    get_statuspage_followup_reminder_delay_minutes,
    get_statuspage_initial_reminder_delay_minutes,
)
from firetower.incidents.models import (
    ExternalLinkType,
    Incident,
)
from firetower.incidents.tasks.decorators import datadog_log
from firetower.integrations.services.slack import SlackService

logger = logging.getLogger(__name__)

MAX_FOLLOWUP_RESCHEDULES = 20

STATUSPAGE_REMINDER_MESSAGE = (
    ":rotating_light: *Statuspage Reminder* :rotating_light:\n"
    "This is a *{severity}* incident. The SLO for posting an initial "
    "Statuspage update is *{slo_minutes} minutes* from declaration. "
    "The SLO will be violated in *{minutes_remaining} minutes*.\n\n"
    "No Statuspage update has been posted yet. "
    "Please run `{slash_command} statuspage` to create a Statuspage incident now."
    "{ic_mention}"
)

STATUSPAGE_FOLLOWUP_REMINDER_MESSAGE = (
    ":rotating_light: *Statuspage Update Reminder* :rotating_light:\n"
    "This is a *{severity}* incident. The next Statuspage update "
    "is due in *{minutes_until_due} minutes*.\n\n"
    "Please run `{slash_command} statuspage` to post a Statuspage update."
    "{ic_mention}"
)


def _build_ic_mention(incident: Incident) -> str:
    if not incident.captain:
        return ""
    slack_id = get_slack_user_id(incident.captain)
    if slack_id:
        return f"\n<@{slack_id}>"

    # If no slack handle, just return empty since we wouldn't be pinging them anyways.
    return ""


@datadog_log
def send_statuspage_reminder(incident_id: int, scheduled_at: str | None = None) -> None:
    slo_minutes = get_statuspage_initial_reminder_delay_minutes()
    if slo_minutes is None:
        return

    try:
        incident = Incident.objects.get(pk=incident_id)
    except Incident.DoesNotExist:
        logger.warning(f"Incident {incident_id} not found for statuspage reminder")
        return

    if incident.is_private:
        return
    if incident.severity not in HIGH_SEVERITIES:
        return
    if incident.status not in ACTIVE_STATUSES:
        return

    has_statuspage = incident.external_links.filter(
        type=ExternalLinkType.STATUSPAGE
    ).exists()
    if has_statuspage:
        return

    status_link = incident.external_links.filter(
        type=ExternalLinkType.SLACK_STATUS
    ).first()
    slack_link = (
        status_link
        or incident.external_links.filter(type=ExternalLinkType.SLACK).first()
    )
    if not slack_link:
        return

    slack = SlackService()
    channel_id = slack.parse_channel_id_from_url(slack_link.url)
    if not channel_id:
        return

    slash_command = settings.SLACK.get("SLASH_COMMAND", "/inc")
    reference_time = (
        datetime.fromisoformat(scheduled_at) if scheduled_at else incident.created_at
    )
    slo_deadline = reference_time + timedelta(minutes=slo_minutes)
    minutes_remaining = max(
        0, int((slo_deadline - timezone.now()).total_seconds() / 60)
    )
    message = STATUSPAGE_REMINDER_MESSAGE.format(
        severity=incident.severity,
        slash_command=slash_command,
        slo_minutes=slo_minutes,
        minutes_remaining=minutes_remaining,
        ic_mention=_build_ic_mention(incident),
    )
    slack.post_message(channel_id, message)


@datadog_log
def send_statuspage_followup_reminder(
    incident_id: int,
    scheduled_at: str | None = None,
    reschedule_count: int = 0,
) -> None:
    followup_minutes = get_statuspage_followup_reminder_delay_minutes()
    if followup_minutes is None:
        return

    try:
        incident = Incident.objects.get(pk=incident_id)
    except Incident.DoesNotExist:
        logger.warning(
            f"Incident {incident_id} not found for statuspage followup reminder"
        )
        return

    if incident.is_private:
        return
    if incident.severity not in HIGH_SEVERITIES:
        return
    if incident.status not in ACTIVE_STATUSES:
        return

    has_statuspage = incident.external_links.filter(
        type=ExternalLinkType.STATUSPAGE
    ).exists()
    if not has_statuspage:
        return

    status_link = incident.external_links.filter(
        type=ExternalLinkType.SLACK_STATUS
    ).first()
    slack_link = (
        status_link
        or incident.external_links.filter(type=ExternalLinkType.SLACK).first()
    )
    if not slack_link:
        return

    slack = SlackService()
    channel_id = slack.parse_channel_id_from_url(slack_link.url)
    if not channel_id:
        return

    reference_time = (
        datetime.fromisoformat(scheduled_at) if scheduled_at else timezone.now()
    )
    deadline = reference_time + timedelta(minutes=followup_minutes)
    minutes_until_due = max(0, int((deadline - timezone.now()).total_seconds() / 60))

    slash_command = settings.SLACK.get("SLASH_COMMAND", "/inc")
    message = STATUSPAGE_FOLLOWUP_REMINDER_MESSAGE.format(
        severity=incident.severity,
        slash_command=slash_command,
        minutes_until_due=minutes_until_due,
        ic_mention=_build_ic_mention(incident),
    )
    try:
        slack.post_message(channel_id, message)
    finally:
        if reschedule_count < MAX_FOLLOWUP_RESCHEDULES:
            try:
                from firetower.incidents.hooks import (  # noqa: PLC0415
                    schedule_statuspage_followup_reminder,
                )

                schedule_statuspage_followup_reminder(
                    incident, reschedule_count=reschedule_count + 1
                )
            except Exception:
                logger.exception(
                    f"Failed to reschedule followup reminder for incident {incident_id}"
                )
