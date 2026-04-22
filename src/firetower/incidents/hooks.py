import logging
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth.models import User

from firetower.auth.models import ExternalProfileType
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from firetower.integrations.services import PagerDutyService, SlackService
from firetower.integrations.services.slack import escape_slack_text

logger = logging.getLogger(__name__)
_slack_service = SlackService()

PAGEABLE_SEVERITIES = {IncidentSeverity.P0, IncidentSeverity.P1}
PAGEABLE_STATUSES = {IncidentStatus.ACTIVE, IncidentStatus.MITIGATED}


@dataclass
class PolicyConfig:
    label: str
    page_label: str
    max_level: int


PAGING_POLICIES: dict[str, PolicyConfig] = {
    "IMOC": PolicyConfig(
        label="On-Call Incident Manager", page_label="IMOC", max_level=1
    ),
    "PROD_ENG": PolicyConfig(
        label="On-Call Prod Eng", page_label="PE On-Call", max_level=2
    ),
}

PD_SUMMARY_MAX_LENGTH = 1024


def _page_if_needed(incident: Incident, channel_id: str | None = None) -> None:
    if incident.severity not in PAGEABLE_SEVERITIES:
        return

    pd_config = settings.PAGERDUTY
    if not pd_config:
        return

    escalation_policies = pd_config.get("ESCALATION_POLICIES", {})

    pd_service = None

    links = [{"href": _build_incident_url(incident), "text": "View in Firetower"}]
    slack_link = incident.external_links.filter(type=ExternalLinkType.SLACK).first()
    if slack_link and slack_link.url:
        links.append({"href": slack_link.url, "text": "Slack Channel"})

    for policy_name, policy_info in PAGING_POLICIES.items():
        policy = escalation_policies.get(policy_name)
        if not policy:
            logger.info(f"No {policy_name} escalation policy configured, skipping page")
            continue

        integration_key = policy.get("integration_key")
        if not integration_key:
            logger.info(
                f"No integration_key for {policy_name} escalation policy, skipping page"
            )
            continue

        if pd_service is None:
            try:
                pd_service = PagerDutyService()
            except Exception:
                logger.exception("Failed to initialize PagerDutyService")
                return

        dedup_key = f"firetower-{incident.incident_number}-{policy_name}"
        page_label = policy_info.page_label
        summary = f"[{page_label}] [{incident.severity}] {incident.incident_number}: {incident.title}"
        summary = summary[:PD_SUMMARY_MAX_LENGTH]

        try:
            success = pd_service.trigger_incident(
                summary, dedup_key, integration_key, links=links
            )
            if not success and channel_id:
                _slack_service.post_message(
                    channel_id,
                    f":warning: Failed to page {page_label} via PagerDuty. Please manually escalate if needed.",
                )
        except Exception:
            logger.exception(f"Failed to page {policy_name} for incident {incident.id}")


def _build_channel_name(incident: Incident) -> str:
    return incident.incident_number.lower()


SLACK_TOPIC_MAX_LENGTH = 250


def _get_slack_user_id(user: User) -> str | None:
    profile = user.external_profiles.filter(type=ExternalProfileType.SLACK).first()
    return profile.external_id if profile else None


def _build_channel_topic(
    incident: Incident, captain_slack_id: str | None = None
) -> str:
    base_url = settings.FIRETOWER_BASE_URL
    incident_url = f"{base_url}/{incident.incident_number}"

    ic_part = ""
    if incident.captain:
        slack_id = (
            captain_slack_id
            if captain_slack_id is not None
            else _get_slack_user_id(incident.captain)
        )
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


def _invite_user_to_channel(
    channel_id: str, user: User, slack_user_id: str | None = None
) -> None:
    try:
        if slack_user_id is None:
            profile = user.external_profiles.filter(
                type=ExternalProfileType.SLACK
            ).first()
            slack_user_id = profile.external_id if profile else None
        if slack_user_id:
            _slack_service.invite_to_channel(channel_id, [slack_user_id])
    except Exception:
        logger.exception(f"Failed to invite user {user.id} to channel {channel_id}")


def _oncall_role_label(
    policy_name: str, policy_label: str, escalation_level: int | None
) -> str:
    if policy_name == "IMOC":
        return policy_label
    if escalation_level == 1:
        return f"{policy_label} (Primary)"
    if escalation_level == 2:
        return f"{policy_label} (Secondary)"
    if escalation_level is not None:
        return f"{policy_label} (Level {escalation_level})"
    return policy_label


def _invite_oncall_users(incident: Incident, channel_id: str) -> None:
    if incident.severity not in PAGEABLE_SEVERITIES:
        return

    pd_config = settings.PAGERDUTY
    if not pd_config:
        return

    api_token = pd_config.get("API_TOKEN")
    if not api_token:
        logger.info("No PagerDuty API token configured, skipping oncall invite")
        return

    escalation_policies = pd_config.get("ESCALATION_POLICIES", {})

    pd_service = None
    role_entries: list[tuple[int, int, str]] = []
    users_to_invite: list[tuple[str, str]] = []

    for policy_index, (policy_name, policy_info) in enumerate(PAGING_POLICIES.items()):
        policy_label = policy_info.label
        max_level = policy_info.max_level
        policy = escalation_policies.get(policy_name)
        if not policy:
            logger.info(
                f"No {policy_name} escalation policy configured, skipping oncall invite"
            )
            continue

        policy_id = policy.get("id")
        if not policy_id:
            logger.info(
                f"No id for {policy_name} escalation policy, skipping oncall invite"
            )
            continue

        if pd_service is None:
            try:
                pd_service = PagerDutyService()
            except Exception:
                logger.exception(
                    "Failed to initialize PagerDutyService for oncall invite"
                )
                return

        try:
            oncall_users = pd_service.get_oncall_users(policy_id)
        except Exception:
            logger.exception(
                f"Failed to fetch oncall users from {policy_name} for incident {incident.id}"
            )
            continue

        for oncall_user in oncall_users:
            email = oncall_user.get("email")
            escalation_level: int | None = oncall_user.get("escalation_level")
            if escalation_level is not None and escalation_level > max_level:
                continue
            if not email:
                continue
            try:
                slack_profile = _slack_service.get_user_profile_by_email(email)
            except Exception:
                logger.exception(f"Failed to look up Slack user for {email}")
                continue

            if not slack_profile or not slack_profile.get("slack_user_id"):
                logger.info(f"Could not find Slack user for oncall email {email}")
                continue

            slack_user_id = slack_profile["slack_user_id"]

            label = _oncall_role_label(policy_name, policy_label, escalation_level)
            sort_level = escalation_level if escalation_level is not None else 999
            role_entries.append(
                (
                    policy_index,
                    sort_level,
                    f"{label}: <@{slack_user_id}>",
                )
            )
            users_to_invite.append((slack_user_id, email))

    if users_to_invite:
        invite_ids = [slack_user_id for slack_user_id, _ in users_to_invite]
        try:
            _slack_service.invite_to_channel(channel_id, invite_ids)
        except Exception:
            logger.exception(
                f"Failed to invite oncall users to channel {channel_id} for incident {incident.id}"
            )

    if role_entries:
        role_entries.sort(key=lambda entry: (entry[0], entry[1]))
        message = "\n".join(line for _, _, line in role_entries)
        try:
            _slack_service.post_message(channel_id, message)
        except Exception:
            logger.exception(
                f"Failed to post oncall role message for incident {incident.id}"
            )


def _create_status_channel(incident: Incident, main_channel_id: str) -> None:
    if incident.severity not in PAGEABLE_SEVERITIES:
        return

    if incident.is_private:
        return

    status_channel_name = f"{incident.incident_number.lower()}-status"
    try:
        status_channel_id = _slack_service.create_channel(
            status_channel_name, is_private=False
        )
    except Exception:
        logger.exception(f"Failed to create status channel for incident {incident.id}")
        return

    if not status_channel_id:
        logger.info(
            f"Status channel {status_channel_name} already exists or could not be created"
        )
        return

    incident_url = _build_incident_url(incident)
    try:
        _slack_service.post_message(
            status_channel_id,
            f"This is the status channel for *{incident.incident_number}*.\n"
            f"For detailed incident information, see <{incident_url}|{incident.incident_number} in Firetower>.\n"
            f"For incident response coordination, join <#{main_channel_id}>.",
        )
    except Exception:
        logger.exception(
            f"Failed to post initial message in status channel for incident {incident.id}"
        )

    users_to_invite: list[str] = []

    if incident.captain:
        captain_slack_id = _get_slack_user_id(incident.captain)
        if captain_slack_id:
            users_to_invite.append(captain_slack_id)

    if incident.reporter:
        reporter_slack_id = _get_slack_user_id(incident.reporter)
        if reporter_slack_id and reporter_slack_id not in users_to_invite:
            users_to_invite.append(reporter_slack_id)

    always_invited = settings.SLACK.get("ALWAYS_INVITED_IDS", [])
    for uid in always_invited:
        if uid not in users_to_invite:
            users_to_invite.append(uid)

    if users_to_invite:
        try:
            _slack_service.invite_to_channel(status_channel_id, users_to_invite)
        except Exception:
            logger.exception(
                f"Failed to invite users to status channel for incident {incident.id}"
            )

    try:
        _slack_service.post_message(
            main_channel_id,
            f"<#{status_channel_id}> has been created for status updates.",
        )
    except Exception:
        logger.exception(
            f"Failed to post status channel link in main channel for incident {incident.id}"
        )


def on_incident_created(incident: Incident) -> None:
    # Use get_or_create to atomically claim the ExternalLink row before calling
    # the Slack API.  If two concurrent requests both reach this point, only one
    # will get created=True; the other bails out without creating a second channel.
    slack_link = None
    created = False
    try:
        slack_link, created = ExternalLink.objects.get_or_create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            defaults={"url": ""},
        )
    except Exception:
        logger.exception(
            f"Failed to get or create Slack ExternalLink for incident {incident.id}"
        )
    channel_id = None
    if not created and slack_link is not None:
        logger.info(
            f"Incident {incident.id} already has a Slack link, skipping channel creation"
        )
    elif created and slack_link is not None:
        try:
            channel_id = _slack_service.create_channel(
                _build_channel_name(incident), is_private=incident.is_private
            )
            if not channel_id:
                slack_link.delete()
                logger.error(
                    f"Failed to create Slack channel for incident {incident.id}"
                )
            else:
                channel_url = _slack_service.build_channel_url(channel_id)
                slack_link.url = channel_url
                slack_link.save(update_fields=["url"])
        except Exception:
            slack_link.delete()
            channel_id = None
            logger.exception(
                f"Failed to create Slack channel for incident {incident.id}"
            )

    # Page P0/P1 early so on-call responders are alerted before we decorate the
    # Slack channel. _page_if_needed reads the Slack link URL from the DB
    # (already saved above), so the PD payload is complete even if channel_id
    # is None here; channel_id is only used to post a fallback warning back to
    # Slack if PD fails.
    try:
        _page_if_needed(incident, channel_id=channel_id)
    except Exception:
        logger.exception(f"Failed to page for incident {incident.id}")

    if channel_id:
        captain_slack_id = (
            _get_slack_user_id(incident.captain) if incident.captain else None
        )

        try:
            _slack_service.set_channel_topic(
                channel_id, _build_channel_topic(incident, captain_slack_id)
            )
        except Exception:
            logger.exception(f"Failed to set channel topic for incident {incident.id}")

        incident_url = _build_incident_url(incident)

        try:
            _slack_service.add_bookmark(channel_id, "Firetower Incident", incident_url)
        except Exception:
            logger.exception(f"Failed to add bookmark for incident {incident.id}")

        guide_message = settings.SLACK.get("INCIDENT_GUIDE_MESSAGE", "")
        if guide_message:
            try:
                _slack_service.post_message(channel_id, guide_message)
            except Exception:
                logger.exception(
                    f"Failed to post guide message for incident {incident.id}"
                )

        ic_mention = ""
        if incident.captain:
            if captain_slack_id:
                ic_mention = f"Incident Captain: <@{captain_slack_id}>"
            else:
                captain_name = escape_slack_text(
                    incident.captain.get_full_name() or incident.captain.username
                )
                ic_mention = f"Incident Captain: {captain_name}"

        if ic_mention:
            try:
                _slack_service.post_message(channel_id, ic_mention)
            except Exception:
                logger.exception(
                    f"Failed to post IC mention for incident {incident.id}"
                )

        if incident.description:
            try:
                _slack_service.post_message(
                    channel_id,
                    f"*Incident Description:*\n{escape_slack_text(incident.description)}",
                )
            except Exception:
                logger.exception(
                    f"Failed to post description for incident {incident.id}"
                )

        ids_to_invite: list[str] = []
        if captain_slack_id:
            ids_to_invite.append(captain_slack_id)

        if incident.reporter:
            reporter_slack_id = _get_slack_user_id(incident.reporter)
            if reporter_slack_id and reporter_slack_id not in ids_to_invite:
                ids_to_invite.append(reporter_slack_id)

        always_invited = settings.SLACK.get("ALWAYS_INVITED_IDS", [])
        for uid in always_invited:
            if uid not in ids_to_invite:
                ids_to_invite.append(uid)

        if ids_to_invite:
            try:
                _slack_service.invite_to_channel(channel_id, ids_to_invite)
            except Exception:
                logger.exception(
                    f"Failed to invite users to channel {channel_id} for incident {incident.id}"
                )

        try:
            _invite_oncall_users(incident, channel_id)
        except Exception:
            logger.exception(
                f"Failed to invite oncall users for incident {incident.id}"
            )

        try:
            _create_status_channel(incident, channel_id)
        except Exception:
            logger.exception(
                f"Failed to create status channel for incident {incident.id}"
            )

        feed_channel_id = settings.SLACK.get("INCIDENT_FEED_CHANNEL_ID", "")
        if feed_channel_id and not incident.is_private:
            feed_message = (
                f"A {incident.severity} incident has been created.\n"
                f"<{incident_url}|{incident.incident_number} {escape_slack_text(incident.title)}>"
                f"\n\nFor those involved, please join <#{channel_id}>"
            )
            try:
                _slack_service.post_message(feed_channel_id, feed_message)
            except Exception:
                logger.exception(
                    f"Failed to post feed channel message for incident {incident.id}"
                )

    # TODO: Datadog notebook creation step will be added in RELENG-467


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
        if channel_id:
            _slack_service.set_channel_topic(channel_id, _build_channel_topic(incident))
            incident_url = _build_incident_url(incident)
            _slack_service.post_message(
                channel_id,
                f"Incident severity updated: {old_severity} -> {incident.severity}\n<{incident_url}|View in Firetower>",
            )
    except Exception:
        logger.exception(f"Error in on_severity_changed for incident {incident.id}")

    if (
        old_severity not in PAGEABLE_SEVERITIES
        and incident.severity in PAGEABLE_SEVERITIES
        and incident.status in PAGEABLE_STATUSES
    ):
        try:
            channel_id = _get_channel_id(incident)
        except Exception:
            logger.exception(f"Failed to get channel id for incident {incident.id}")
            channel_id = None

        try:
            _page_if_needed(incident, channel_id=channel_id)
        except Exception:
            logger.exception(f"Failed to page for incident {incident.id}")

        if channel_id:
            try:
                _invite_oncall_users(incident, channel_id)
            except Exception:
                logger.exception(
                    f"Failed to invite oncall users for incident {incident.id}"
                )

            try:
                _create_status_channel(incident, channel_id)
            except Exception:
                logger.exception(
                    f"Failed to create status channel for incident {incident.id}"
                )


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
