import logging

from django.conf import settings
from django.contrib.auth.models import User

from firetower.auth.models import ExternalProfileType
from firetower.incidents.models import ExternalLink, ExternalLinkType, Incident
from firetower.integrations.services import SlackService
from firetower.integrations.services.slack import escape_slack_text

logger = logging.getLogger(__name__)
_slack_service = SlackService()


def _build_channel_name(incident: Incident) -> str:
    return incident.incident_number.lower()


SLACK_TOPIC_MAX_LENGTH = 250


def _get_slack_user_id(user: User) -> str | None:
    profile = user.external_profiles.filter(type=ExternalProfileType.SLACK).first()
    return profile.external_id if profile else None


def _build_channel_topic(incident: Incident) -> str:
    base_url = settings.FIRETOWER_BASE_URL
    incident_url = f"{base_url}/{incident.incident_number}"

    ic_part = ""
    if incident.captain:
        slack_id = _get_slack_user_id(incident.captain)
        if slack_id:
            ic_part = f" | IC: <@{slack_id}>"
        else:
            captain_name = incident.captain.get_full_name() or incident.captain.username
            ic_part = f" | IC: {escape_slack_text(captain_name)}"

    prefix = f"[{incident.severity}] "
    suffix = ic_part
    # Link text: "INC-2000 title"
    link_label_prefix = f"{incident.incident_number} "
    link_overhead = len(f"<{incident_url}|{link_label_prefix}>")
    max_title_len = max(
        SLACK_TOPIC_MAX_LENGTH - len(prefix) - len(suffix) - link_overhead, 0
    )
    title = escape_slack_text(incident.title)
    if len(title) > max_title_len:
        title = (title[: max_title_len - 1] + "\u2026") if max_title_len > 0 else ""
    topic = f"{prefix}<{incident_url}|{link_label_prefix}{title}>{suffix}"
    return topic[:SLACK_TOPIC_MAX_LENGTH]


def _build_incident_url(incident: Incident) -> str:
    return f"{settings.FIRETOWER_BASE_URL}/{incident.incident_number}"


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

        channel_id = _slack_service.create_channel(
            _build_channel_name(incident), is_private=incident.is_private
        )
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

        incident_url = _build_incident_url(incident)
        _slack_service.add_bookmark(channel_id, "Firetower Incident", incident_url)

        guide_message = settings.SLACK.get("INCIDENT_GUIDE_MESSAGE", "")
        if guide_message:
            _slack_service.post_message(channel_id, guide_message)

        ic_mention = ""
        if incident.captain:
            slack_id = _get_slack_user_id(incident.captain)
            if slack_id:
                ic_mention = f"\nIncident Captain: <@{slack_id}>"
            else:
                captain_name = escape_slack_text(
                    incident.captain.get_full_name() or incident.captain.username
                )
                ic_mention = f"\nIncident Captain: {captain_name}"

        _slack_service.post_message(
            channel_id,
            f"*{incident.incident_number}: {escape_slack_text(incident.title)}*\n"
            f"Severity: {incident.severity} | Status: {incident.status}"
            f"{ic_mention}",
        )

        if incident.description:
            _slack_service.post_message(
                channel_id,
                f"*Incident Description:*\n{escape_slack_text(incident.description)}",
            )

        if incident.captain:
            _invite_user_to_channel(channel_id, incident.captain)

        always_invited = settings.SLACK.get("ALWAYS_INVITED_IDS", [])
        if always_invited:
            _slack_service.invite_to_channel(channel_id, always_invited)

        feed_channel_id = settings.SLACK.get("INCIDENT_FEED_CHANNEL_ID", "")
        if feed_channel_id and not incident.is_private:
            incident_url = _build_incident_url(incident)
            feed_message = (
                f"A {incident.severity} incident has been created.\n"
                f"<{incident_url}|{incident.incident_number} {escape_slack_text(incident.title)}>"
                f"\n\nFor those involved, please join <#{channel_id}>"
            )
            _slack_service.post_message(feed_channel_id, feed_message)

        # TODO: Datadog notebook creation step will be added in RELENG-467
    except Exception:
        logger.exception(f"Error in on_incident_created for incident {incident.id}")


def on_status_changed(incident: Incident, old_status: str) -> None:
    try:
        channel_id = _get_channel_id(incident)
        if not channel_id:
            return

        incident_url = _build_incident_url(incident)
        _slack_service.post_message(
            channel_id,
            f"Incident status updated: {old_status} -> {incident.status}\n<{incident_url}|View in Firetower>",
        )
    except Exception:
        logger.exception(f"Error in on_status_changed for incident {incident.id}")


def on_severity_changed(incident: Incident, old_severity: str) -> None:
    try:
        channel_id = _get_channel_id(incident)
        if not channel_id:
            return

        _slack_service.set_channel_topic(channel_id, _build_channel_topic(incident))
        incident_url = _build_incident_url(incident)
        _slack_service.post_message(
            channel_id,
            f"Incident severity updated: {old_severity} -> {incident.severity}\n<{incident_url}|View in Firetower>",
        )
    except Exception:
        logger.exception(f"Error in on_severity_changed for incident {incident.id}")


def on_title_changed(incident: Incident) -> None:
    try:
        channel_id = _get_channel_id(incident)
        if not channel_id:
            return

        _slack_service.set_channel_topic(channel_id, _build_channel_topic(incident))
    except Exception:
        logger.exception(f"Error in on_title_changed for incident {incident.id}")


def on_visibility_changed(incident: Incident) -> None:
    try:
        channel_id = _get_channel_id(incident)
        if not channel_id:
            return

        visibility = "private" if incident.is_private else "public"
        incident_url = _build_incident_url(incident)
        message = (
            f"This incident has been marked as *{visibility}* in Firetower. "
            f"If you want to make this channel {visibility}, you will need a Slack admin to make the change.\n"
            f"<{incident_url}|View in Firetower>"
        )
        _slack_service.post_message(channel_id, message)
    except Exception:
        logger.exception(f"Error in on_visibility_changed for incident {incident.id}")


def on_captain_changed(incident: Incident) -> None:
    try:
        channel_id = _get_channel_id(incident)
        if not channel_id:
            return

        _slack_service.set_channel_topic(channel_id, _build_channel_topic(incident))

        incident_url = _build_incident_url(incident)
        if incident.captain:
            slack_id = _get_slack_user_id(incident.captain)
            if slack_id:
                captain_ref = f"<@{slack_id}>"
            else:
                captain_ref = escape_slack_text(
                    incident.captain.get_full_name() or incident.captain.username
                )
            _slack_service.post_message(
                channel_id,
                f"Incident captain updated to {captain_ref}\n<{incident_url}|View in Firetower>",
            )
            _invite_user_to_channel(channel_id, incident.captain)
    except Exception:
        logger.exception(f"Error in on_captain_changed for incident {incident.id}")
