import logging
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

# Per-tier minimum incident age (in days) before we nag, and the settings.LINEAR
# key holding the comment for that tier.
# Linear priority values: 1 = Urgent (P0), 2 = High (P1), 3 = Medium (P2).
ACTION_ITEM_NAG_TIERS: dict[int, tuple[int, str]] = {
    1: (7, "ACTION_ITEM_NAG_COMMENT_HIGH_PRIORITY"),
    2: (7, "ACTION_ITEM_NAG_COMMENT_HIGH_PRIORITY"),
    3: (21, "ACTION_ITEM_NAG_COMMENT_MEDIUM_PRIORITY"),
}
ACTION_ITEM_REMINDER_PRIORITIES = tuple(ACTION_ITEM_NAG_TIERS.keys())

_NAG_TEMPLATE_ENV = Environment(autoescape=False)

# Per-tier minimum incident age (in days) before we nag, and the settings.LINEAR
# key holding the comment for that tier.
# Linear priority values: 1 = Urgent (P0), 2 = High (P1), 3 = Medium (P2).
ACTION_ITEM_NAG_TIERS: dict[int, tuple[int, str]] = {
    1: (7, "ACTION_ITEM_NAG_COMMENT_HIGH_PRIORITY"),
    2: (7, "ACTION_ITEM_NAG_COMMENT_HIGH_PRIORITY"),
    3: (21, "ACTION_ITEM_NAG_COMMENT_MEDIUM_PRIORITY"),
}
ACTION_ITEM_REMINDER_PRIORITIES = tuple(ACTION_ITEM_NAG_TIERS.keys())


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

    def _nag(action_item: ActionItem, incident: Incident) -> None:
        template_source = comments_by_priority[action_item.priority]
        tier_min_age_days, _ = ACTION_ITEM_NAG_TIERS[action_item.priority]
        incident_age_days = (timezone.now() - incident.created_at).days
        try:
            comment = _NAG_TEMPLATE_ENV.from_string(template_source).render(
                slo_days=tier_min_age_days,
                incident_age_days=incident_age_days,
                days_past_due=max(0, incident_age_days - tier_min_age_days),
                days_left=max(0, tier_min_age_days - incident_age_days),
                slo_passed=incident_age_days >= tier_min_age_days,
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
