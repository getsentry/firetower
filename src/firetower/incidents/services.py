import logging
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from firetower.auth.services import get_or_create_user_from_slack_id
from firetower.incidents.models import ExternalLinkType, Incident
from firetower.integrations.services import SlackService

logger = logging.getLogger(__name__)
_slack_service = SlackService()


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
            error_msg = f"Could not get/create user for Slack ID: {slack_user_id}"
            logger.warning(error_msg)
            stats.errors.append(error_msg)
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
