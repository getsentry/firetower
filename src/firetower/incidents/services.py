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
from firetower.incidents.models import ActionItem, ExternalLinkType, Incident
from firetower.integrations.services import LinearService, SlackService

logger = logging.getLogger(__name__)
_slack_service = SlackService()
_linear_service = LinearService()


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


def _resolve_assignee_by_email(email: str) -> User | None:
    user = get_or_create_user_from_email(email)
    if not user:
        return None
    ExternalProfile.objects.get_or_create(
        user=user,
        type=ExternalProfileType.LINEAR,
        defaults={"external_id": email},
    )
    return user


def sync_action_items_from_linear(
    incident: Incident, force: bool = False
) -> ActionItemsSyncStats:
    stats = ActionItemsSyncStats()

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

    firetower_url = (
        f"{settings.FIRETOWER_BASE_URL}/{settings.PROJECT_KEY}-{incident.id}"
    )
    issues = _linear_service.get_issues_by_attachment_url(firetower_url)

    if issues is None:
        error_msg = f"Failed to fetch Linear issues for incident {incident.id}"
        logger.error(error_msg)
        stats.errors.append(error_msg)
        return stats

    logger.info(f"Syncing {len(issues)} Linear issues to incident {incident.id}")

    seen_linear_ids: set[str] = set()

    for issue in issues:
        seen_linear_ids.add(issue["id"])

        assignee = None
        if issue.get("assignee_email"):
            assignee = _resolve_assignee_by_email(issue["assignee_email"])

        _, created = ActionItem.objects.update_or_create(
            linear_issue_id=issue["id"],
            defaults={
                "incident": incident,
                "linear_identifier": issue["identifier"],
                "title": issue["title"],
                "status": issue["status"],
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

    logger.info(
        f"Action item sync complete for incident {incident.id}: "
        f"{stats.created} created, {stats.updated} updated, {stats.deleted} deleted"
    )

    return stats
