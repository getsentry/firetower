import logging
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.auth.services import (
    get_or_create_user_from_email,
    get_or_create_user_from_slack_id,
)
from firetower.incidents.models import (
    ActionItem,
    ActionItemStatus,
    ExternalLinkType,
    Incident,
)
from firetower.integrations.services import LinearService, SlackService

logger = logging.getLogger(__name__)
_slack_service = SlackService()
_linear_service: LinearService | None = None


def _get_linear_service() -> LinearService:
    global _linear_service  # noqa: PLW0603
    if _linear_service is None:
        _linear_service = LinearService()
    return _linear_service


@dataclass
class ParticipantsSyncStats:
    """Statistics from a participant sync operation."""

    added: int = 0
    already_existed: int = 0
    errors: list[str] = field(default_factory=list)
    skipped: bool = False


def sync_incident_participants_from_slack(
    incident: Incident, force: bool = False
) -> ParticipantsSyncStats:
    """
    Sync incident participants from Slack channel members.

    Args:
        incident: Incident instance to sync
        force: If True, bypass throttle and force sync

    Returns:
        ParticipantsSyncStats dataclass with sync statistics
    """
    stats = ParticipantsSyncStats()

    if not force and incident.participants_last_synced_at:
        time_since_sync = timezone.now() - incident.participants_last_synced_at
        if time_since_sync < timedelta(
            seconds=settings.PARTICIPANT_SYNC_THROTTLE_SECONDS
        ):
            logger.info(
                f"Skipping sync for incident {incident.id} - synced {time_since_sync.total_seconds():.0f}s ago"
            )
            stats.skipped = True
            return stats

    slack_link = incident.external_links.filter(type=ExternalLinkType.SLACK).first()

    if not slack_link:
        error_msg = f"No Slack link found for incident {incident.id}"
        logger.warning(error_msg)
        stats.errors.append(error_msg)
        return stats

    channel_id = _slack_service.parse_channel_id_from_url(slack_link.url)

    if not channel_id:
        error_msg = f"Could not parse channel ID from URL: {slack_link.url}"
        logger.warning(error_msg)
        stats.errors.append(error_msg)
        return stats

    slack_member_ids = _slack_service.get_channel_members(channel_id)

    if slack_member_ids is None:
        error_msg = f"Failed to fetch channel members for {channel_id}"
        logger.error(error_msg)
        stats.errors.append(error_msg)
        return stats

    logger.info(
        f"Syncing {len(slack_member_ids)} Slack members to incident {incident.id}"
    )

    existing_participant_ids = set(incident.participants.values_list("id", flat=True))
    new_participants = []

    for slack_user_id in slack_member_ids:
        if slack_user_id.startswith("B"):
            logger.info(f"Skipping bot: {slack_user_id}")
            continue

        user = get_or_create_user_from_slack_id(slack_user_id)

        if not user:
            logger.info(
                f"Skipping Slack user {slack_user_id} - could not resolve to a Firetower user"
            )
            continue

        if not user.is_active:
            continue

        if user.id in existing_participant_ids:
            stats.already_existed += 1
        else:
            new_participants.append(user)
            stats.added += 1

    if new_participants:
        incident.participants.add(*new_participants)
        logger.info(
            f"Added {len(new_participants)} new participants to incident {incident.id}"
        )

    incident.participants_last_synced_at = timezone.now()
    incident.save(update_fields=["participants_last_synced_at"])

    logger.info(
        f"Sync complete for incident {incident.id}: {stats.added} added, "
        f"{stats.already_existed} already existed, {len(stats.errors)} errors"
    )

    return stats


@dataclass
class ActionItemsSyncStats:
    created: int = 0
    updated: int = 0
    deleted: int = 0
    errors: list[str] = field(default_factory=list)
    skipped: bool = False


def _resolve_assignees(
    issues: dict[str, dict],
) -> dict[str, User | None]:
    email_to_linear_id: dict[str, str | None] = {}
    for issue in issues.values():
        email = issue.get("assignee_email")
        if email:
            email_to_linear_id[email] = issue.get("assignee_linear_id")

    if not email_to_linear_id:
        return {}

    existing_users = {
        u.email: u for u in User.objects.filter(email__in=email_to_linear_id.keys())
    }

    resolved: dict[str, User | None] = {}
    for email, linear_id in email_to_linear_id.items():
        user = existing_users.get(email)
        if not user:
            user = get_or_create_user_from_email(email)
        if not user:
            resolved[email] = None
            continue
        resolved[email] = user
        if linear_id:
            ExternalProfile.objects.update_or_create(
                user=user,
                type=ExternalProfileType.LINEAR,
                defaults={"external_id": linear_id},
            )

    return resolved


COMPLETED_STATUSES = {ActionItemStatus.DONE, ActionItemStatus.CANCELLED}


def _update_parent_issue_status(
    incident: Incident, linear_service: LinearService
) -> None:
    team_id = settings.LINEAR.get("TEAM_ID")
    if not team_id or not incident.linear_parent_issue_id:
        return

    statuses = list(incident.action_items.values_list("status", flat=True))
    if not statuses:
        return

    all_complete = all(s in COMPLETED_STATUSES for s in statuses)

    states = linear_service.get_workflow_states(team_id)
    if not states:
        return

    if all_complete:
        completed_state_id = states.get("completed")
        if completed_state_id:
            linear_service.update_issue(
                incident.linear_parent_issue_id, state_id=completed_state_id
            )


def sync_action_items_from_linear(
    incident: Incident, force: bool = False
) -> ActionItemsSyncStats:
    stats = ActionItemsSyncStats()

    if not incident.linear_parent_issue_id:
        stats.skipped = True
        return stats

    if not force and incident.action_items_last_synced_at:
        time_since_sync = timezone.now() - incident.action_items_last_synced_at
        if time_since_sync < timedelta(
            seconds=settings.ACTION_ITEM_SYNC_THROTTLE_SECONDS
        ):
            logger.info(
                f"Skipping action item sync for incident {incident.id} - synced {time_since_sync.total_seconds():.0f}s ago"
            )
            stats.skipped = True
            return stats

    linear_service = _get_linear_service()
    parent_id = incident.linear_parent_issue_id

    children = linear_service.get_child_issues(parent_id)
    if children is None:
        error_msg = f"Failed to fetch child issues for incident {incident.id}"
        logger.error(error_msg)
        stats.errors.append(error_msg)
        incident.action_items_last_synced_at = timezone.now()
        incident.save(update_fields=["action_items_last_synced_at"])
        return stats

    related = linear_service.get_related_issues(parent_id)
    if related is None:
        error_msg = f"Failed to fetch related issues for incident {incident.id}"
        logger.error(error_msg)
        stats.errors.append(error_msg)
        incident.action_items_last_synced_at = timezone.now()
        incident.save(update_fields=["action_items_last_synced_at"])
        return stats

    all_issues: dict[str, dict] = {}
    for issue in children:
        all_issues[issue["id"]] = issue
    for issue in related:
        if issue["id"] not in all_issues:
            all_issues[issue["id"]] = issue

    logger.info(f"Syncing {len(all_issues)} Linear issues to incident {incident.id}")

    assignee_map = _resolve_assignees(all_issues)
    seen_linear_ids: set[str] = set()

    for issue in all_issues.values():
        seen_linear_ids.add(issue["id"])

        assignee = assignee_map.get(issue.get("assignee_email", ""))

        _, created = ActionItem.objects.update_or_create(
            incident=incident,
            linear_issue_id=issue["id"],
            defaults={
                "linear_identifier": issue["identifier"],
                "title": issue["title"],
                "status": issue["status"],
                "relation_type": issue["relation_type"],
                "assignee": assignee,
                "url": issue["url"],
            },
        )

        if created:
            stats.created += 1
        else:
            stats.updated += 1

    deleted_count, _ = (
        ActionItem.objects.filter(incident=incident)
        .exclude(linear_issue_id__in=seen_linear_ids)
        .delete()
    )
    stats.deleted = deleted_count

    incident.action_items_last_synced_at = timezone.now()
    incident.save(update_fields=["action_items_last_synced_at"])

    try:
        _update_parent_issue_status(incident, linear_service)
    except Exception:
        logger.exception(
            f"Failed to update Linear parent issue status for incident {incident.id}"
        )

    logger.info(
        f"Action item sync complete for incident {incident.id}: "
        f"{stats.created} created, {stats.updated} updated, {stats.deleted} deleted"
    )

    return stats
