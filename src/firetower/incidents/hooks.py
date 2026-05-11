import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction

from firetower.auth.models import ExternalProfileType
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from firetower.integrations.services import (
    DatadogService,
    LinearService,
    PagerDutyService,
    SlackService,
)
from firetower.integrations.services.notion import NotionService
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


@dataclass
class ChannelSetupContext:
    """Primitive-arg context shared by normal and fallback incident channel setup."""

    channel_id: str
    channel_name: str
    title: str
    severity: str
    is_private: bool
    captain_slack_id: str | None = None
    captain_name: str | None = None
    reporter_slack_id: str | None = None
    description: str | None = None
    incident_url: str | None = None
    incident_number: str | None = None


def page_for_channel(
    severity: str,
    dedup_prefix: str,
    title: str,
    slack_service: SlackService,
    *,
    links: list[dict[str, str]] | None = None,
    channel_id: str | None = None,
    is_private: bool = False,
) -> set[str]:
    """Trigger PD pages for pageable severities. No DB access.

    Returns the set of policy names that were successfully paged.
    """
    paged: set[str] = set()

    if severity not in PAGEABLE_SEVERITIES:
        return paged

    pd_config = settings.PAGERDUTY
    if not pd_config:
        return paged

    escalation_policies = pd_config.get("ESCALATION_POLICIES", {})

    pd_service = None

    policies_to_page = (
        {"IMOC": PAGING_POLICIES["IMOC"]} if is_private else PAGING_POLICIES
    )
    title = "Private Incident" if is_private else title

    for policy_name, policy_info in policies_to_page.items():
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
                return paged

        dedup_key = f"firetower-{dedup_prefix}-{policy_name}"
        page_label = policy_info.page_label
        summary = f"[{page_label}] [{severity}] {dedup_prefix}: {title}"
        summary = summary[:PD_SUMMARY_MAX_LENGTH]

        try:
            success = pd_service.trigger_incident(
                summary, dedup_key, integration_key, links=links or []
            )
            if success:
                paged.add(policy_name)
            elif channel_id:
                slack_service.post_message(
                    channel_id,
                    f":warning: Failed to page {page_label} via PagerDuty. Please manually escalate if needed.",
                )
        except Exception:
            logger.exception(f"Failed to page {policy_name} for {dedup_prefix}")

    return paged


def _page_if_needed(incident: Incident, channel_id: str | None = None) -> set[str]:
    links: list[dict[str, str]] = [
        {"href": _build_incident_url(incident), "text": "View in Firetower"}
    ]
    if channel_id:
        links.append(
            {
                "href": _slack_service.build_channel_url(channel_id),
                "text": "Slack Channel",
            }
        )
    return page_for_channel(
        incident.severity,
        incident.incident_number,
        incident.title,
        _slack_service,
        links=links,
        channel_id=channel_id,
        is_private=incident.is_private,
    )


def build_channel_name(incident: Incident) -> str:
    return incident.incident_number.lower()


SLACK_TOPIC_MAX_LENGTH = 250


def _get_slack_user_id(user: User) -> str | None:
    profile = user.external_profiles.filter(type=ExternalProfileType.SLACK).first()
    return profile.external_id if profile else None


def build_channel_topic(incident: Incident, captain_slack_id: str | None = None) -> str:
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


def _invite_oncall_to_channel(
    severity: str,
    channel_id: str,
    slack_service: SlackService,
    *,
    is_private: bool = False,
    paged_policies: set[str] | None = None,
) -> None:
    """Invite on-call users to a channel. No DB access."""
    if severity not in PAGEABLE_SEVERITIES:
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

    policies_to_invite = (
        {"IMOC": PAGING_POLICIES["IMOC"]} if is_private else PAGING_POLICIES
    )

    for policy_index, (policy_name, policy_info) in enumerate(
        policies_to_invite.items()
    ):
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
                f"Failed to fetch oncall users from {policy_name} for channel {channel_id}"
            )
            continue

        oncall_users.sort(key=lambda u: u.get("escalation_level") or 999)
        seen_emails: set[str] = set()
        for oncall_user in oncall_users:
            email = oncall_user.get("email")
            escalation_level: int | None = oncall_user.get("escalation_level")
            if escalation_level is not None and escalation_level > max_level:
                continue
            if not email or email in seen_emails:
                continue
            seen_emails.add(email)
            try:
                slack_profile = slack_service.get_user_profile_by_email(email)
            except Exception:
                logger.exception(f"Failed to look up Slack user for {email}")
                continue

            if not slack_profile or not slack_profile.get("slack_user_id"):
                logger.info(f"Could not find Slack user for oncall email {email}")
                continue

            slack_user_id = slack_profile["slack_user_id"]

            label = _oncall_role_label(policy_name, policy_label, escalation_level)
            paged_suffix = (
                " (paged)"
                if paged_policies
                and policy_name in paged_policies
                and escalation_level == 1
                else ""
            )
            sort_level = escalation_level if escalation_level is not None else 999
            role_entries.append(
                (
                    policy_index,
                    sort_level,
                    f"{label}: <@{slack_user_id}>{paged_suffix}",
                )
            )
            users_to_invite.append((slack_user_id, email))

    if users_to_invite:
        invite_ids = [slack_user_id for slack_user_id, _ in users_to_invite]
        try:
            slack_service.invite_to_channel(channel_id, invite_ids)
        except Exception:
            logger.exception(f"Failed to invite oncall users to channel {channel_id}")

    if role_entries:
        role_entries.sort(key=lambda entry: (entry[0], entry[1]))
        message = "\n".join(line for _, _, line in role_entries)
        try:
            slack_service.post_message(channel_id, message)
        except Exception:
            logger.exception(
                f"Failed to post oncall role message in channel {channel_id}"
            )


def _invite_oncall_users(
    incident: Incident,
    channel_id: str,
    paged_policies: set[str] | None = None,
) -> None:
    _invite_oncall_to_channel(
        incident.severity,
        channel_id,
        _slack_service,
        is_private=incident.is_private,
        paged_policies=paged_policies,
    )


def _create_status_channel_for_context(
    ctx: ChannelSetupContext, slack_service: SlackService
) -> None:
    """Create a companion status channel. No DB access."""
    if ctx.severity not in PAGEABLE_SEVERITIES:
        return

    if ctx.is_private:
        return

    status_channel_name = f"{ctx.channel_name}-status"
    try:
        status_channel_id = slack_service.create_channel(
            status_channel_name, is_private=False
        )
    except Exception:
        logger.exception(f"Failed to create status channel {status_channel_name}")
        return

    if not status_channel_id:
        logger.info(
            f"Status channel {status_channel_name} already exists or could not be created"
        )
        return

    label = ctx.incident_number or ctx.channel_name
    message_lines = [f"This is the status channel for *{label}*."]
    if ctx.incident_url and ctx.incident_number:
        message_lines.append(
            f"For detailed incident information, see "
            f"<{ctx.incident_url}|{ctx.incident_number} in Firetower>."
        )
    message_lines.append(
        f"For incident response coordination, join <#{ctx.channel_id}>."
    )
    try:
        slack_service.post_message(status_channel_id, "\n".join(message_lines))
    except Exception:
        logger.exception(
            f"Failed to post initial message in status channel {status_channel_name}"
        )

    users_to_invite: list[str] = []
    if ctx.captain_slack_id:
        users_to_invite.append(ctx.captain_slack_id)
    if ctx.reporter_slack_id and ctx.reporter_slack_id not in users_to_invite:
        users_to_invite.append(ctx.reporter_slack_id)

    always_invited = settings.SLACK.get("ALWAYS_INVITED_IDS", [])
    for uid in always_invited:
        if uid not in users_to_invite:
            users_to_invite.append(uid)

    if users_to_invite:
        try:
            slack_service.invite_to_channel(status_channel_id, users_to_invite)
        except Exception:
            logger.exception(
                f"Failed to invite users to status channel {status_channel_name}"
            )

    try:
        slack_service.post_message(
            ctx.channel_id,
            f"<#{status_channel_id}> has been created for status updates.",
        )
    except Exception:
        logger.exception(f"Failed to post status channel link in {ctx.channel_name}")


def _create_status_channel(incident: Incident, main_channel_id: str) -> None:
    captain_slack_id = (
        _get_slack_user_id(incident.captain) if incident.captain else None
    )
    reporter_slack_id = (
        _get_slack_user_id(incident.reporter) if incident.reporter else None
    )
    ctx = ChannelSetupContext(
        channel_id=main_channel_id,
        channel_name=incident.incident_number.lower(),
        title=incident.title,
        severity=incident.severity,
        is_private=incident.is_private,
        captain_slack_id=captain_slack_id,
        reporter_slack_id=reporter_slack_id,
        incident_url=_build_incident_url(incident),
        incident_number=incident.incident_number,
    )
    _create_status_channel_for_context(ctx, _slack_service)


def _do_create_datadog_notebook(
    channel_name: str,
    title: str,
) -> str | None:
    """Create a Datadog notebook via the API.

    Returns the notebook URL on success, None otherwise.
    """
    service = DatadogService()
    if not service.configured:
        logger.info(
            "DatadogService not configured, skipping notebook for %s", channel_name
        )
        return None

    notebook_url = service.create_notebook(channel_name, title)
    if not notebook_url:
        logger.info("Datadog notebook creation returned no URL for %s", channel_name)
        return None

    return notebook_url


def _notify_datadog_notebook(
    channel_id: str,
    notebook_url: str,
    channel_name: str,
    slack_service: SlackService,
) -> None:
    """Post bookmark and message for a created Datadog notebook."""
    try:
        slack_service.add_bookmark(channel_id, "Datadog Notebook", notebook_url)
    except Exception:
        logger.exception(f"Failed to add Datadog bookmark for {channel_name}")
    try:
        slack_service.post_message(
            channel_id,
            f"Datadog notebook created: {notebook_url}",
        )
    except Exception:
        logger.exception(f"Failed to post Datadog notebook message for {channel_name}")


def _create_datadog_notebook(incident: Incident, channel_id: str) -> None:
    try:
        if incident.is_private:
            logger.info(f"Skipping Datadog notebook for private incident {incident.id}")
            try:
                _slack_service.post_message(
                    channel_id,
                    "Datadog notebook creation skipped due to private incident.",
                )
            except Exception:
                logger.exception(
                    f"Failed to post Datadog skip message for incident {incident.id}"
                )
            return

        notebook_url: str | None = None
        with transaction.atomic():
            # Hold the row lock across the Datadog API call so concurrent runs
            # serialize and only one notebook is created. A placeholder row is
            # inserted up front so select_for_update has something to lock.
            # Trade-off: a stuck Datadog API blocks DB writers on this row
            # until REQUEST_TIMEOUT_SECONDS.
            link, created = ExternalLink.objects.select_for_update().get_or_create(
                incident=incident,
                type=ExternalLinkType.DATADOG,
                defaults={"url": ""},
            )
            if not created and link.url:
                logger.info(
                    f"Incident {incident.id} already has a Datadog notebook, skipping"
                )
                return

            notebook_url = _do_create_datadog_notebook(
                incident.incident_number,
                incident.title,
            )
            if not notebook_url:
                link.delete()
                return

            link.url = notebook_url
            link.save(update_fields=["url"])

        _notify_datadog_notebook(
            channel_id, notebook_url, incident.incident_number, _slack_service
        )
    except Exception:
        logger.exception(
            f"Failed to create Datadog notebook for incident {incident.id}"
        )


def _do_create_troubleshooting_doc(
    channel_name: str,
    incident_url: str | None,
) -> dict | None:
    """Create a Notion troubleshooting page via the API.

    Returns the Notion page dict on success, None otherwise.
    """
    if not NotionService.is_troubleshooting_configured():
        logger.info(
            "Notion troubleshooting not configured, skipping for %s", channel_name
        )
        return None

    notion = NotionService.for_troubleshooting()
    if not notion:
        logger.warning(
            "NotionService.for_troubleshooting() returned None for %s", channel_name
        )
        return None

    page = notion.create_troubleshooting_page(channel_name, incident_url)
    if not page or not page.get("url"):
        logger.error(
            "Troubleshooting doc creation returned no URL for %s", channel_name
        )
        return None

    return page


def _notify_troubleshooting_doc(
    channel_id: str,
    page_url: str,
    channel_name: str,
    slack_service: SlackService,
) -> None:
    """Post bookmark and message for a created troubleshooting doc."""
    try:
        slack_service.add_bookmark(channel_id, "Troubleshooting Doc", page_url)
    except Exception:
        logger.exception(
            "Failed to add troubleshooting doc bookmark for %s", channel_name
        )
    try:
        slack_service.post_message(
            channel_id,
            f"A <{page_url}|Clinical Troubleshooting document> has been created. "
            "Please use this to keep track of Symptoms, Hypothesis, and Actions "
            "as you're investigating this incident.",
        )
    except Exception:
        logger.exception(
            "Failed to post troubleshooting doc message for %s", channel_name
        )


def _create_troubleshooting_doc(incident: Incident, channel_id: str) -> None:
    try:
        if incident.is_private:
            logger.info(
                "Skipping troubleshooting doc for private incident %s", incident.id
            )
            try:
                _slack_service.post_message(
                    channel_id,
                    "Troubleshooting doc creation skipped due to private incident.",
                )
            except Exception:
                logger.exception(
                    "Failed to post troubleshooting skip message for incident %s",
                    incident.id,
                )
            return

        with transaction.atomic():
            link, created = ExternalLink.objects.select_for_update().get_or_create(
                incident=incident,
                type=ExternalLinkType.NOTION_TROUBLESHOOTING,
                defaults={"url": ""},
            )
            if not created:
                if link.url:
                    logger.info(
                        "Incident %s already has a troubleshooting doc, skipping",
                        incident.id,
                    )
                else:
                    logger.info(
                        "Incident %s troubleshooting doc creation already in progress, skipping",
                        incident.id,
                    )
                return

        # Notion API calls happen outside the transaction to avoid holding the
        # SELECT FOR UPDATE lock while making slow external requests.
        incident_url = _build_incident_url(incident)
        page = _do_create_troubleshooting_doc(incident.incident_number, incident_url)
        if not page:
            ExternalLink.objects.filter(
                incident=incident,
                type=ExternalLinkType.NOTION_TROUBLESHOOTING,
                url="",
            ).delete()
            return

        with transaction.atomic():
            link = ExternalLink.objects.select_for_update().get(
                incident=incident,
                type=ExternalLinkType.NOTION_TROUBLESHOOTING,
            )
            if link.url:
                logger.warning(
                    "Race condition: concurrent call already created troubleshooting doc for %s",
                    incident.incident_number,
                )
                return
            link.url = page["url"]
            link.save(update_fields=["url"])

        _notify_troubleshooting_doc(
            channel_id, page["url"], incident.incident_number, _slack_service
        )
    except Exception:
        logger.exception(
            "Failed to create troubleshooting doc for incident %s", incident.id
        )
        ExternalLink.objects.filter(
            incident=incident,
            type=ExternalLinkType.NOTION_TROUBLESHOOTING,
            url="",
        ).delete()


def decorate_incident_channel(
    ctx: ChannelSetupContext,
    slack_service: SlackService,
    *,
    skip_datadog: bool = False,
    skip_notion: bool = False,
    paged_policies: set[str] | None = None,
) -> None:
    """
    Shared channel setup called by both the normal and fallback creation paths.

    When adding a new channel decoration step, add it here so both paths get it.
    The normal path passes skip_datadog=True and skip_notion=True because it
    handles those with DB-dedup logic before calling this function.
    """
    guide_message = settings.SLACK.get("INCIDENT_GUIDE_MESSAGE", "")
    if guide_message:
        try:
            slack_service.post_message(ctx.channel_id, guide_message)
        except Exception:
            logger.exception(f"Failed to post guide message in {ctx.channel_name}")

    if not skip_datadog:
        if ctx.is_private:
            try:
                slack_service.post_message(
                    ctx.channel_id,
                    "Datadog notebook creation skipped due to private incident.",
                )
            except Exception:
                logger.exception(
                    f"Failed to post Datadog skip message in {ctx.channel_name}"
                )
        else:
            try:
                notebook_url = _do_create_datadog_notebook(ctx.channel_name, ctx.title)
                if notebook_url:
                    _notify_datadog_notebook(
                        ctx.channel_id, notebook_url, ctx.channel_name, slack_service
                    )
            except Exception:
                logger.exception(
                    f"Failed to create Datadog notebook for {ctx.channel_name}"
                )

    if not skip_notion:
        if ctx.is_private:
            try:
                slack_service.post_message(
                    ctx.channel_id,
                    "Troubleshooting doc creation skipped due to private incident.",
                )
            except Exception:
                logger.exception(
                    f"Failed to post troubleshooting skip message in {ctx.channel_name}"
                )
        else:
            try:
                page = _do_create_troubleshooting_doc(
                    ctx.channel_name, ctx.incident_url
                )
                if page:
                    _notify_troubleshooting_doc(
                        ctx.channel_id,
                        page["url"],
                        ctx.channel_name,
                        slack_service,
                    )
            except Exception:
                logger.exception(
                    f"Failed to create troubleshooting doc for {ctx.channel_name}"
                )

    if ctx.captain_slack_id:
        try:
            slack_service.post_message(
                ctx.channel_id,
                f"Incident Captain: <@{ctx.captain_slack_id}>",
            )
        except Exception:
            logger.exception(f"Failed to post IC mention in {ctx.channel_name}")
    elif ctx.captain_name:
        try:
            slack_service.post_message(
                ctx.channel_id,
                f"Incident Captain: {escape_slack_text(ctx.captain_name)}",
            )
        except Exception:
            logger.exception(f"Failed to post IC mention in {ctx.channel_name}")

    if ctx.description:
        try:
            slack_service.post_message(
                ctx.channel_id,
                f"*Incident Description:*\n{escape_slack_text(ctx.description)}",
            )
        except Exception:
            logger.exception(f"Failed to post description in {ctx.channel_name}")

    ids_to_invite: list[str] = []
    if ctx.captain_slack_id:
        ids_to_invite.append(ctx.captain_slack_id)
    if ctx.reporter_slack_id and ctx.reporter_slack_id not in ids_to_invite:
        ids_to_invite.append(ctx.reporter_slack_id)
    always_invited = settings.SLACK.get("ALWAYS_INVITED_IDS", [])
    for uid in always_invited:
        if uid not in ids_to_invite:
            ids_to_invite.append(uid)
    if ids_to_invite:
        try:
            slack_service.invite_to_channel(ctx.channel_id, ids_to_invite)
        except Exception:
            logger.exception(f"Failed to invite users to {ctx.channel_name}")

    try:
        _invite_oncall_to_channel(
            ctx.severity,
            ctx.channel_id,
            slack_service,
            is_private=ctx.is_private,
            paged_policies=paged_policies,
        )
    except Exception:
        logger.exception(f"Failed to invite oncall users to {ctx.channel_name}")

    try:
        _create_status_channel_for_context(ctx, slack_service)
    except Exception:
        logger.exception(f"Failed to create status channel for {ctx.channel_name}")

    feed_channel_id = settings.SLACK.get("INCIDENT_FEED_CHANNEL_ID", "")
    if feed_channel_id and not ctx.is_private:
        try:
            if ctx.incident_url and ctx.incident_number:
                feed_message = (
                    f"A {ctx.severity} incident has been created.\n"
                    f"<{ctx.incident_url}|{ctx.incident_number} "
                    f"{escape_slack_text(ctx.title)}>"
                    f"\n\nFor those involved, please join <#{ctx.channel_id}>"
                )
            else:
                feed_message = (
                    f"A {ctx.severity} incident has been created "
                    "(degraded mode).\n"
                    f"{escape_slack_text(ctx.title)}"
                    f"\n\nFor those involved, please join <#{ctx.channel_id}>"
                )
            slack_service.post_message(feed_channel_id, feed_message)
        except Exception:
            logger.exception(f"Failed to post to feed channel for {ctx.channel_name}")


def _linear_issue_title(incident: Incident) -> str:
    if incident.is_private:
        return f"[{incident.incident_number}] Private Incident"
    return f"[{incident.incident_number}] {incident.title}"


LINEAR_PARENT_DESCRIPTION = (
    "Relate action items to this ticket to have them tracked by Firetower. "
    "Child issues or other relations (related, blocking, etc.) will all work. "
    "Do not update title or captain here, use Firetower for that."
)


MAX_CLAIM_ATTEMPTS = 5


def _claim_linear_issue(
    linear_service: LinearService,
    incident: Incident,
    team_id: str,
    project_id: str | None,
) -> dict[str, Any] | None:
    identifier = incident.incident_number

    for _ in range(MAX_CLAIM_ATTEMPTS):
        issue = linear_service.get_issue(identifier)
        if issue:
            return issue
        linear_service.create_issue("Placeholder", "", team_id, project_id)

    return None


def _create_linear_parent_issue(incident: Incident) -> None:
    team_id = str(settings.LINEAR.get("TEAM_ID", ""))
    if not team_id:
        return

    linear_link, created = ExternalLink.objects.get_or_create(
        incident=incident,
        type=ExternalLinkType.LINEAR,
        defaults={"url": ""},
    )
    if not created:
        logger.info(f"Incident {incident.id} already has a Linear link, skipping")
        return

    try:
        linear_service = LinearService()
        project_id = str(settings.LINEAR.get("PROJECT_ID", "")) or None
        sync_identifiers = settings.LINEAR.get("SYNC_IDENTIFIERS", False)
        title = _linear_issue_title(incident)

        if sync_identifiers:
            issue = _claim_linear_issue(linear_service, incident, team_id, project_id)
            if not issue:
                linear_link.delete()
                logger.warning(
                    f"Failed to claim Linear issue for incident {incident.id}"
                )
                return

            states = linear_service.get_workflow_states(team_id)
            started_state_id = states.get("started") if states else None
            linear_service.update_issue(
                issue["id"],
                title=title,
                description=LINEAR_PARENT_DESCRIPTION,
                state_id=started_state_id,
            )
        else:
            issue = linear_service.create_issue(
                title, LINEAR_PARENT_DESCRIPTION, team_id, project_id
            )
            if not issue:
                linear_link.delete()
                logger.warning(
                    f"Failed to create Linear issue for incident {incident.id}"
                )
                return

        linear_link.url = issue["url"]
        linear_link.save(update_fields=["url"])

        incident.linear_parent_issue_id = issue["id"]
        incident.save(update_fields=["linear_parent_issue_id"])
    except Exception:
        linear_link.delete()
        logger.exception(
            f"Failed to create Linear parent issue for incident {incident.id}"
        )
        return

    try:
        incident_url = _build_incident_url(incident)
        linear_service.create_attachment(
            issue["id"], incident_url, f"Firetower: {incident.incident_number}"
        )
    except Exception:
        logger.exception(
            f"Failed to create Linear attachment for incident {incident.id}"
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
                build_channel_name(incident), is_private=incident.is_private
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
    paged_policies: set[str] = set()
    try:
        paged_policies = _page_if_needed(incident, channel_id=channel_id)
    except Exception:
        logger.exception(f"Failed to page for incident {incident.id}")

    if channel_id:
        captain_slack_id = (
            _get_slack_user_id(incident.captain) if incident.captain else None
        )

        try:
            _slack_service.set_channel_topic(
                channel_id, build_channel_topic(incident, captain_slack_id)
            )
        except Exception:
            logger.exception(f"Failed to set channel topic for incident {incident.id}")

        incident_url = _build_incident_url(incident)

        try:
            _slack_service.add_bookmark(channel_id, "Firetower Incident", incident_url)
        except Exception:
            logger.exception(f"Failed to add bookmark for incident {incident.id}")

        captain_name = None
        if incident.captain and not captain_slack_id:
            captain_name = incident.captain.get_full_name() or incident.captain.username

        reporter_slack_id = (
            _get_slack_user_id(incident.reporter) if incident.reporter else None
        )

        ctx = ChannelSetupContext(
            channel_id=channel_id,
            channel_name=incident.incident_number.lower(),
            title=incident.title,
            severity=incident.severity,
            is_private=incident.is_private,
            captain_slack_id=captain_slack_id,
            captain_name=captain_name,
            reporter_slack_id=reporter_slack_id,
            description=incident.description,
            incident_url=incident_url,
            incident_number=incident.incident_number,
        )
        decorate_incident_channel(
            ctx,
            _slack_service,
            skip_datadog=True,
            skip_notion=True,
            paged_policies=paged_policies,
        )

        # DB-dedup Datadog/Notion after shared decoration so the guide message
        # appears first in the channel.
        _create_datadog_notebook(incident, channel_id)
        _create_troubleshooting_doc(incident, channel_id)

    try:
        _create_linear_parent_issue(incident)
    except Exception:
        logger.exception(
            f"Failed to create Linear parent issue for incident {incident.id}"
        )


def on_status_changed(incident: Incident, old_status: str) -> None:
    channel_id: str | None = None
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

    if (
        incident.status
        in (IncidentStatus.MITIGATED, IncidentStatus.DONE, IncidentStatus.POSTMORTEM)
        and channel_id
    ):
        try:
            from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415
            from firetower.slack_app.handlers.dumpslack import (  # noqa: PLC0415
                trigger_slack_dump_async,
            )

            trigger_slack_dump_async(get_bolt_app().client, channel_id, incident)
        except Exception:
            logger.exception(f"Failed to trigger slack dump for incident {incident.id}")


def on_severity_changed(incident: Incident, old_severity: str) -> None:
    try:
        channel_id = _get_channel_id(incident)
        if channel_id:
            _slack_service.set_channel_topic(channel_id, build_channel_topic(incident))
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

        paged_policies: set[str] = set()
        try:
            paged_policies = _page_if_needed(incident, channel_id=channel_id)
        except Exception:
            logger.exception(f"Failed to page for incident {incident.id}")

        if channel_id:
            try:
                _invite_oncall_users(
                    incident, channel_id, paged_policies=paged_policies
                )
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
        if channel_id:
            _slack_service.set_channel_topic(channel_id, build_channel_topic(incident))
    except Exception:
        logger.exception(f"Error in on_title_changed for incident {incident.id}")

    if incident.linear_parent_issue_id:
        try:
            linear_service = LinearService()
            linear_service.update_issue(
                incident.linear_parent_issue_id,
                title=_linear_issue_title(incident),
            )
        except Exception:
            logger.exception(
                f"Failed to update Linear issue title for incident {incident.id}"
            )


def on_visibility_changed(incident: Incident) -> None:
    try:
        channel_id = _get_channel_id(incident)
        if channel_id:
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

    if incident.linear_parent_issue_id:
        try:
            linear_service = LinearService()
            linear_service.update_issue(
                incident.linear_parent_issue_id,
                title=_linear_issue_title(incident),
            )
        except Exception:
            logger.exception(
                f"Failed to update Linear issue title for incident {incident.id}"
            )


def on_captain_changed(incident: Incident) -> None:
    try:
        channel_id = _get_channel_id(incident)
        if not channel_id:
            return

        _slack_service.set_channel_topic(channel_id, build_channel_topic(incident))

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
