import logging

from django.conf import settings
from django.contrib.auth.models import User

from firetower.auth.models import ExternalProfileType
from firetower.incidents.models import ExternalLink, ExternalLinkType, Incident
from firetower.integrations.services import SlackService

logger = logging.getLogger(__name__)
_slack_service = SlackService()


def _build_channel_name(incident: Incident) -> str:
    return incident.incident_number.lower()


SLACK_TOPIC_MAX_LENGTH = 250


def _build_channel_topic(incident: Incident) -> str:
    captain_name = ""
    if incident.captain:
        captain_name = incident.captain.get_full_name() or incident.captain.username
    prefix = f"[{incident.severity}] {incident.incident_number} "
    suffix = f" | IC: @{captain_name}"
    max_title_len = max(SLACK_TOPIC_MAX_LENGTH - len(prefix) - len(suffix), 0)
    title = incident.title
    if len(title) > max_title_len:
        title = title[: max_title_len - 1] + "\u2026" if max_title_len > 0 else ""
    topic = f"{prefix}{title}{suffix}"
    return topic[:SLACK_TOPIC_MAX_LENGTH]


def _get_channel_id(incident: Incident) -> str | None:
    slack_link = incident.external_links.filter(type=ExternalLinkType.SLACK).first()
    if not slack_link:
        return None
    return _slack_service.parse_channel_id_from_url(slack_link.url)


def _invite_user_to_channel(channel_id: str, user: User) -> None:
    try:
        slack_profile = user.external_profiles.filter(
            type=ExternalProfileType.SLACK
        ).first()
        if slack_profile:
            _slack_service.invite_to_channel(channel_id, [slack_profile.external_id])
    except Exception:
        logger.exception(f"Failed to invite user {user.id} to channel {channel_id}")


def on_incident_created(incident: Incident) -> None:
    try:
        existing_slack_link = incident.external_links.filter(
            type=ExternalLinkType.SLACK
        ).exists()
        if existing_slack_link:
            logger.info(
                f"Incident {incident.id} already has a Slack link, skipping channel creation"
            )
            return

        channel_id = _slack_service.create_channel(_build_channel_name(incident))
        if not channel_id:
            logger.warning(f"Failed to create Slack channel for incident {incident.id}")
            return

        channel_url = _slack_service.build_channel_url(channel_id)
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url=channel_url,
        )

        _slack_service.set_channel_topic(channel_id, _build_channel_topic(incident))

        base_url = settings.FIRETOWER_BASE_URL
        incident_url = f"{base_url}/incidents/{incident.incident_number}"
        _slack_service.add_bookmark(channel_id, "Firetower Incident", incident_url)

        _slack_service.post_message(
            channel_id,
            f"*{incident.incident_number}: {incident.title}*\n"
            f"Severity: {incident.severity} | Status: {incident.status}",
        )

        if incident.captain:
            _invite_user_to_channel(channel_id, incident.captain)

        # TODO: Datadog notebook creation step will be added in RELENG-467
    except Exception:
        logger.exception(f"Error in on_incident_created for incident {incident.id}")


def on_status_changed(incident: Incident, old_status: str) -> None:
    try:
        channel_id = _get_channel_id(incident)
        if not channel_id:
            return

        _slack_service.post_message(
            channel_id,
            f"Status changed: {old_status} -> {incident.status}",
        )
        _slack_service.set_channel_topic(channel_id, _build_channel_topic(incident))
    except Exception:
        logger.exception(f"Error in on_status_changed for incident {incident.id}")


def on_severity_changed(incident: Incident, old_severity: str) -> None:
    try:
        channel_id = _get_channel_id(incident)
        if not channel_id:
            return

        _slack_service.post_message(
            channel_id,
            f"Severity changed: {old_severity} -> {incident.severity}",
        )
        _slack_service.set_channel_topic(channel_id, _build_channel_topic(incident))
    except Exception:
        logger.exception(f"Error in on_severity_changed for incident {incident.id}")


def on_title_changed(incident: Incident, old_title: str) -> None:
    try:
        channel_id = _get_channel_id(incident)
        if not channel_id:
            return

        _slack_service.post_message(
            channel_id,
            f"Title changed: {old_title} -> {incident.title}",
        )
        _slack_service.set_channel_topic(channel_id, _build_channel_topic(incident))
    except Exception:
        logger.exception(f"Error in on_title_changed for incident {incident.id}")


def on_captain_changed(incident: Incident) -> None:
    try:
        channel_id = _get_channel_id(incident)
        if not channel_id:
            return

        _slack_service.set_channel_topic(channel_id, _build_channel_topic(incident))

        captain_name = ""
        if incident.captain:
            captain_name = incident.captain.get_full_name() or incident.captain.username
        _slack_service.post_message(
            channel_id,
            f"Incident captain changed to @{captain_name}",
        )

        if incident.captain:
            _invite_user_to_channel(channel_id, incident.captain)
    except Exception:
        logger.exception(f"Error in on_captain_changed for incident {incident.id}")
