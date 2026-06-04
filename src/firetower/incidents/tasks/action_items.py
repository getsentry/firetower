import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from jinja2 import Environment, TemplateError

from firetower.incidents.hooks import HIGH_SEVERITIES
from firetower.incidents.models import (
    ActionItem,
    ActionItemStatus,
    Incident,
    IncidentStatus,
)
from firetower.incidents.services import sync_action_items_from_linear
from firetower.incidents.tasks.decorators import datadog_log
from firetower.integrations.services.linear import LinearService

logger = logging.getLogger(__name__)

ACTION_ITEM_REMINDER_MAX_AGE_DAYS = 90
ACTION_ITEM_REMINDER_NAG_EVERY_DAYS = 7


# Linear priority values: 1 = Urgent (P0), 2 = High (P1), 3 = Medium (P2).
HIGH_PRIORITY_VALUES = (1, 2)
MEDIUM_PRIORITY_VALUES = (3,)
ACTION_ITEM_REMINDER_PRIORITIES = HIGH_PRIORITY_VALUES + MEDIUM_PRIORITY_VALUES


@dataclass(frozen=True)
class NagTier:
    slo_days: int
    comment_setting_key: str


def _build_nag_tiers(linear: dict) -> dict[int, NagTier]:
    candidates: list[tuple[tuple[int, ...], NagTier]] = [
        (
            HIGH_PRIORITY_VALUES,
            NagTier(
                slo_days=linear.get("ACTION_ITEM_SLO_DAYS_HIGH_PRIORITY", 14),
                comment_setting_key="ACTION_ITEM_NAG_COMMENT_HIGH_PRIORITY",
            ),
        ),
        (
            MEDIUM_PRIORITY_VALUES,
            NagTier(
                slo_days=linear.get("ACTION_ITEM_SLO_DAYS_MEDIUM_PRIORITY", 30),
                comment_setting_key="ACTION_ITEM_NAG_COMMENT_MEDIUM_PRIORITY",
            ),
        ),
    ]
    tiers: dict[int, NagTier] = {}
    for priorities, tier in candidates:
        if tier.slo_days < ACTION_ITEM_REMINDER_NAG_EVERY_DAYS:
            logger.warning(
                "Skipping %s nag tier: configured SLO of %d day(s) is below "
                "the %d-day nag cadence",
                tier.comment_setting_key,
                tier.slo_days,
                ACTION_ITEM_REMINDER_NAG_EVERY_DAYS,
            )
            continue
        tiers.update(dict.fromkeys(priorities, tier))
    return tiers


_NAG_TEMPLATE_ENV = Environment(autoescape=False)


@datadog_log
def send_action_item_reminder() -> None:
    linear = settings.LINEAR or {}
    nag_tiers = _build_nag_tiers(linear)
    comments_by_priority: dict[int, str] = {
        priority: linear.get(tier.comment_setting_key, "")
        for priority, tier in nag_tiers.items()
    }
    if not any(comments_by_priority.values()):
        logger.warning("No Linear nag comments configured, skipping job")
        return

    now = timezone.now()
    earliest_notify_after_days = (
        min(tier.slo_days for tier in nag_tiers.values())
        - ACTION_ITEM_REMINDER_NAG_EVERY_DAYS
    )
    min_age = now - timedelta(days=ACTION_ITEM_REMINDER_MAX_AGE_DAYS)
    max_age = now - timedelta(days=earliest_notify_after_days)

    def _action_item_eligible(action_item: ActionItem, incident: Incident) -> bool:
        if action_item.status not in [
            ActionItemStatus.TODO,
            ActionItemStatus.IN_PROGRESS,
        ]:
            return False
        tier = nag_tiers.get(action_item.priority)
        if not tier:
            return False
        if not comments_by_priority.get(action_item.priority):
            return False
        notify_after_days = tier.slo_days - ACTION_ITEM_REMINDER_NAG_EVERY_DAYS
        if incident.created_at > now - timedelta(days=notify_after_days):
            return False
        if action_item.last_nag is None:
            return True
        return action_item.last_nag < (
            now - timedelta(days=ACTION_ITEM_REMINDER_NAG_EVERY_DAYS)
        )

    def _nag(action_item: ActionItem, incident: Incident) -> None:
        template_source = comments_by_priority[action_item.priority]
        tier = nag_tiers[action_item.priority]
        incident_age_days = (timezone.now() - incident.created_at).days
        try:
            comment = _NAG_TEMPLATE_ENV.from_string(template_source).render(
                slo_days=tier.slo_days,
                incident_age_days=incident_age_days,
                days_past_due=max(0, incident_age_days - tier.slo_days),
                days_left=max(0, tier.slo_days - incident_age_days),
                slo_passed=incident_age_days >= tier.slo_days,
                action_item=action_item,
                incident=incident,
            )
        except TemplateError:
            logger.exception(
                f"Failed to render nag comment template for action item {action_item.linear_identifier}"
            )
            return
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
            _nag(action_item, incident)
