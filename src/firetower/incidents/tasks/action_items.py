import logging
from dataclasses import dataclass
from datetime import timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from django.conf import settings
from django.utils import timezone
from jinja2 import Environment, TemplateError

from firetower.auth.models import ExternalProfileType
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
from firetower.integrations.services.slack import SlackService, escape_slack_text

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

MISFILED_ACTION_ITEM_REMINDER_MARKER = "Firetower action-item team reminder"


def _remind_misfiled_action_item_creators(linear: dict) -> None:
    if not linear.get("SYNC_IDENTIFIERS", False):
        return

    team_id = linear.get("TEAM_ID")
    if not team_id:
        return

    try:
        service = LinearService()
        issues = service.get_misfiled_action_items(
            team_id, MISFILED_ACTION_ITEM_REMINDER_MARKER
        )
    except Exception:
        logger.info(
            "Failed to fetch misfiled action items from Linear; skipping team reminders",
            exc_info=True,
        )
        return
    if issues is None:
        logger.info(
            "Failed to fetch misfiled action items from Linear; skipping team reminders"
        )
        return

    logger.info(
        "Found %d misfiled action items without a team reminder in Linear team %s",
        len(issues),
        team_id,
    )
    for issue in issues:
        issue_id = None
        try:
            issue_id = issue["id"]
            creator = issue.get("creator")
            greeting = (
                f"Hi @[{creator['displayName']}]({creator['id']}), "
                if creator
                else "Hi, "
            )
            comment = (
                f"**{MISFILED_ACTION_ITEM_REMINDER_MARKER}**\n\n"
                f"{greeting}this action item was created in the "
                f"{settings.PROJECT_KEY} team. Please move it to the relevant "
                "actioning team, keeping it as a child of the incident ticket. "
                "The incident team is reserved for incident tickets, not action items."
            )
            # A stable UUID in Linear's required v4 format also prevents duplicate
            # comments from overlapping runs or a successful but timed-out request.
            comment_id = str(
                UUID(
                    bytes=uuid5(
                        NAMESPACE_URL, f"firetower:inc-team-reminder:{issue_id}"
                    ).bytes,
                    version=4,
                )
            )
            success = service.create_comment(issue_id, comment, comment_id=comment_id)
        except Exception:
            logger.info(
                "Failed to post team reminder for action item %s",
                issue_id,
                exc_info=True,
            )
            continue
        if not success:
            logger.info("Failed to post team reminder for action item %s", issue_id)
        else:
            logger.info("Posted team reminder for action item %s", issue_id)


@datadog_log
def send_action_item_reminder() -> None:
    linear = settings.LINEAR or {}
    nag_tiers = _build_nag_tiers(linear)
    comments_by_priority: dict[int, str] = {
        priority: linear.get(tier.comment_setting_key, "")
        for priority, tier in nag_tiers.items()
    }
    if not any(comments_by_priority.values()):
        logger.warning("No Linear nag comments configured, skipping SLO reminders")
        _remind_misfiled_action_item_creators(linear)
        return

    now = timezone.now()
    min_age = now - timedelta(days=ACTION_ITEM_REMINDER_MAX_AGE_DAYS)

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
        if action_item.created_at > now - timedelta(days=notify_after_days):
            return False
        if action_item.last_nag is None:
            return True
        return action_item.last_nag < (
            now - timedelta(days=ACTION_ITEM_REMINDER_NAG_EVERY_DAYS)
        )

    def _send_slack_nag_dm(
        action_item: ActionItem, incident: Incident, message: str
    ) -> None:
        recipient = action_item.assignee or incident.captain
        if recipient is None:
            logger.info(
                "No assignee or captain for action item %s, skipping Slack DM",
                action_item.linear_identifier,
            )
            return

        profile = recipient.external_profiles.filter(
            type=ExternalProfileType.SLACK
        ).first()
        if profile is None:
            logger.info(
                "No Slack profile for user %s, skipping DM for action item %s",
                recipient.email or recipient.username,
                action_item.linear_identifier,
            )
            return

        slack_message = (
            f"<{action_item.url}|{action_item.linear_identifier}>: "
            f"{escape_slack_text(action_item.title)}\n\n{message}"
        )

        try:
            SlackService().post_message(profile.external_id, slack_message)
        except Exception:
            logger.exception(
                "Failed to send Slack nag DM for action item %s",
                action_item.linear_identifier,
            )

    def _nag(action_item: ActionItem, incident: Incident) -> None:
        template_source = comments_by_priority[action_item.priority]
        tier = nag_tiers[action_item.priority]
        incident_age_days = (timezone.now() - incident.created_at).days
        action_item_age_days = (timezone.now() - action_item.created_at).days
        slo_passed = action_item_age_days >= tier.slo_days
        try:
            comment = _NAG_TEMPLATE_ENV.from_string(template_source).render(
                slo_days=tier.slo_days,
                incident_age_days=incident_age_days,
                action_item_age_days=action_item_age_days,
                days_past_due=max(0, action_item_age_days - tier.slo_days),
                days_left=max(0, tier.slo_days - action_item_age_days),
                slo_passed=slo_passed,
                action_item=action_item,
                incident=incident,
            )
        except TemplateError:
            logger.exception(
                f"Failed to render nag comment template for action item {action_item.linear_identifier}"
            )
            return
        linear_service = LinearService()
        try:
            success = linear_service.create_comment(
                action_item.linear_issue_id, comment
            )
        except Exception:
            logger.exception(
                f"Failed to post nag comment for action item {action_item.linear_identifier}"
            )
            return
        if not success:
            return

        if slo_passed:
            _send_slack_nag_dm(action_item, incident, comment)

        action_item.last_nag = timezone.now()
        action_item.save(update_fields=["last_nag"])

    incidents = Incident.objects.filter(
        created_at__gte=min_age,
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

    _remind_misfiled_action_item_creators(linear)
