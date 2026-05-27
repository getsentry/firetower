import functools
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Protocol

from datadog import statsd
from django.conf import settings
from django.utils import timezone
from django_q.tasks import Schedule

from firetower.incidents.hooks import (
    ACTIVE_STATUSES,
    HIGH_SEVERITIES,
    get_statuspage_followup_reminder_delay_minutes,
    get_statuspage_initial_reminder_delay_minutes,
)
from firetower.incidents.models import (
    ExternalLinkType,
    Incident,
)
from firetower.integrations.services.slack import SlackService

SCHEDULES = {
    "schedule_demo": {
        "func": "firetower.incidents.tasks.schedule_demo",
        "schedule_type": Schedule.MINUTES,  # Minutes
        "minutes": 5,
        "repeats": -1,  # repeat indefinitely
    },
}

DATADOG_INVALID_CHARS = re.compile(r"[^A-Za-z0-9-_.\/]")


logger = logging.getLogger(__name__)


class NamedFunction(Protocol):
    __name__: str

    def __call__(self, *args: Any, **kwargs: Any) -> None: ...


def datadog_log(f: NamedFunction) -> NamedFunction:
    task_name: str = DATADOG_INVALID_CHARS.sub("_", f.__name__)
    tags = [f"task:{task_name}"]

    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        statsd.increment("django_q.task.run", 1, tags)
        try:
            f(*args, **kwargs)
        except Exception as e:
            statsd.increment("django_q.task.error", 1, tags)
            logger.error(
                f"Error while executing task '{task_name}': {e}", exc_info=True
            )
            raise e
        else:
            statsd.increment("django_q.task.success", 1, tags)
        finally:
            # TODO(taylor-osler-sentry): Figure out if/why this is necessary?
            try:
                statsd.flush()
            except Exception as e:
                logger.error(
                    f"Error while flushing datadog metrics: {e}", exc_info=True
                )
                # Don't re-raise; it's more important we raise the inner exception, if present

    return wrapper


@datadog_log
def schedule_demo() -> None:
    incident = Incident.objects.order_by("-created_at").first()
    if incident:
        title = "Private Incident" if incident.is_private else incident.title
        logger.info(f"Most recent incident: INC-{incident.id}: {title}")
    else:
        logger.info("No incidents found.")


MAX_FOLLOWUP_RESCHEDULES = 48

STATUSPAGE_REMINDER_MESSAGE = (
    ":rotating_light: *Statuspage Reminder* :rotating_light:\n"
    "This is a *{severity}* incident. The SLO for posting an initial "
    "Statuspage update is *{slo_minutes} minutes* from declaration. "
    "The SLO will be violated in *{minutes_remaining} minutes*.\n\n"
    "No Statuspage update has been posted yet. "
    "Please run `{slash_command} statuspage` to create a Statuspage incident now."
)

STATUSPAGE_FOLLOWUP_REMINDER_MESSAGE = (
    ":rotating_light: *Statuspage Update Reminder* :rotating_light:\n"
    "This is a *{severity}* incident. The next Statuspage update "
    "is due in *{minutes_until_due} minutes*.\n\n"
    "Please run `{slash_command} statuspage` to post a Statuspage update."
)


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
    )
    try:
        slack.post_message(channel_id, message)
    finally:
        if reschedule_count < MAX_FOLLOWUP_RESCHEDULES:
            from firetower.incidents.hooks import (  # noqa: PLC0415
                schedule_statuspage_followup_reminder,
            )

            schedule_statuspage_followup_reminder(
                incident, reschedule_count=reschedule_count + 1
            )
