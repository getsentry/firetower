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
    get_slack_user_id,
    get_statuspage_followup_reminder_delay_minutes,
    get_statuspage_initial_reminder_delay_minutes,
)
from firetower.incidents.models import (
    ActionItem,
    ActionItemStatus,
    ExternalLinkType,
    Incident,
    IncidentStatus,
)
from firetower.incidents.services import sync_action_items_from_linear
from firetower.integrations.services.linear import LinearService
from firetower.integrations.services.slack import SlackService

SCHEDULES = {
    "schedule_demo": {
        "func": "firetower.incidents.tasks.schedule_demo",
        "schedule_type": Schedule.MINUTES,  # Minutes
        "minutes": 5,
        "repeats": -1,  # repeat indefinitely
    },
    "send_action_item_reminder": {
        "func": "firetower.incidents.tasks.send_action_item_reminder",
        "schedule_type": Schedule.MINUTES,
        "minutes": 30,
        "repeats": -1,
    },
}

ACTION_ITEM_REMINDER_MAX_AGE_DAYS = 90
ACTION_ITEM_REMINDER_NAG_EVERY_DAYS = 7

# Per-tier minimum incident age (in days) before we nag, and the settings.LINEAR
# key holding the comment for that tier.
# Linear priority values: 1 = Urgent (P0), 2 = High (P1), 3 = Medium (P2).
ACTION_ITEM_NAG_TIERS: dict[int, tuple[int, str]] = {
    1: (7, "ACTION_ITEM_NAG_COMMENT_HIGH_PRIORITY"),
    2: (7, "ACTION_ITEM_NAG_COMMENT_HIGH_PRIORITY"),
    3: (21, "ACTION_ITEM_NAG_COMMENT_MEDIUM_PRIORITY"),
}
ACTION_ITEM_REMINDER_PRIORITIES = tuple(ACTION_ITEM_NAG_TIERS.keys())

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

    return wrapper


@datadog_log
def schedule_demo() -> None:
    incident = Incident.objects.order_by("-created_at").first()
    if incident:
        title = "Private Incident" if incident.is_private else incident.title
        logger.info(f"Most recent incident: INC-{incident.id}: {title}")
    else:
        logger.info("No incidents found.")


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


@datadog_log
def send_action_item_reminder() -> None:
    linear = settings.LINEAR or {}
    comments_by_priority: dict[int, str] = {
        priority: linear.get(setting_key, "")
        for priority, (_, setting_key) in ACTION_ITEM_NAG_TIERS.items()
    }
    if not any(comments_by_priority.values()):
        logger.warning("No Linear nag comments configured, skipping job")
        return

    now = timezone.now()
    earliest_min_age_days = min(
        min_age for min_age, _ in ACTION_ITEM_NAG_TIERS.values()
    )
    min_age = now - timedelta(days=ACTION_ITEM_REMINDER_MAX_AGE_DAYS)
    max_age = now - timedelta(days=earliest_min_age_days)

    def _action_item_eligible(action_item: ActionItem, incident: Incident) -> bool:
        if action_item.status not in [
            ActionItemStatus.TODO,
            ActionItemStatus.IN_PROGRESS,
        ]:
            return False
        tier = ACTION_ITEM_NAG_TIERS.get(action_item.priority)
        if not tier:
            return False
        tier_min_age_days, _ = tier
        if not comments_by_priority.get(action_item.priority):
            return False
        if incident.created_at > now - timedelta(days=tier_min_age_days):
            return False
        if action_item.last_nag is None:
            return True
        return action_item.last_nag < (
            now - timedelta(days=ACTION_ITEM_REMINDER_NAG_EVERY_DAYS)
        )

    def _nag(action_item: ActionItem) -> None:
        comment = comments_by_priority[action_item.priority]
        try:
            success = LinearService().create_comment(
                action_item.linear_issue_id, comment
            )
        except Exception:
            logger.exception(
                f"Failed to post nag comment for action item {action_item.linear_identifier}"
            )
            return
        if success:
            action_item.last_nag = timezone.now()
            action_item.save(update_fields=["last_nag"])

    incidents = Incident.objects.filter(
        created_at__gte=min_age,
        created_at__lte=max_age,
        severity__in=HIGH_SEVERITIES,
    ).exclude(status=IncidentStatus.CANCELED)

    for incident in incidents:
        try:
            sync_action_items_from_linear(incident)
        except Exception:
            logger.exception(
                f"Failed to refresh action items for incident {incident.id}"
            )
            continue

        action_items = incident.action_items.filter(
            priority__in=ACTION_ITEM_REMINDER_PRIORITIES
        )

        eligible: list[ActionItem] = [
            action_item
            for action_item in action_items
            if _action_item_eligible(action_item, incident)
        ]

        for action_item in eligible:
            _nag(action_item)
