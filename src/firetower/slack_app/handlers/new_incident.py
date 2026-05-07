import logging
import uuid
from typing import Any

from django.conf import settings

from firetower.auth.services import get_or_create_user_from_slack_id
from firetower.incidents.models import IncidentSeverity, Tag, TagType
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.integrations.services import SlackService
from firetower.integrations.services.slack import escape_slack_text

logger = logging.getLogger(__name__)
_slack_service = SlackService()

_DEFAULT_SEVERITY = IncidentSeverity.P3

_FALLBACK_PAGEABLE_SEVERITIES = {"P0", "P1"}


def _create_fallback_channel(client: Any, slack_user_id: str, form_data: dict) -> None:
    title = form_data["title"]
    severity = form_data["severity"]
    description = form_data.get("description", "")
    impact_summary = form_data.get("impact_summary", "")
    captain_slack_id = form_data.get("captain_slack_id")
    is_private = form_data.get("is_private", False)
    impact_type_tags = form_data.get("impact_type_tags", [])
    affected_service_tags = form_data.get("affected_service_tags", [])
    affected_region_tags = form_data.get("affected_region_tags", [])

    channel_name = f"inc-{uuid.uuid4().hex[:8]}"

    channel_id = _slack_service.create_channel(channel_name, is_private=is_private)
    if not channel_id:
        logger.error("Fallback channel creation failed for %s", channel_name)
        client.chat_postMessage(
            channel=slack_user_id,
            text=(
                "Something went wrong creating your incident. "
                "Please create a Slack channel manually for incident coordination "
                "and let #team-sre know."
            ),
        )
        return

    # Post and pin metadata for backfill
    metadata_lines = [
        "Incident Metadata (for backfill):",
        f"Title: {title}",
        f"Severity: {severity}",
    ]
    if description:
        metadata_lines.append(f"Description: {description}")
    if impact_summary:
        metadata_lines.append(f"Impact Summary: {impact_summary}")
    if captain_slack_id:
        metadata_lines.append(f"Captain: <@{captain_slack_id}>")
    metadata_lines.append(f"Reporter: <@{slack_user_id}>")
    metadata_lines.append(f"Private: {'yes' if is_private else 'no'}")
    if impact_type_tags:
        metadata_lines.append(f"Impact Types: {', '.join(impact_type_tags)}")
    if affected_service_tags:
        metadata_lines.append(f"Affected Services: {', '.join(affected_service_tags)}")
    if affected_region_tags:
        metadata_lines.append(f"Affected Regions: {', '.join(affected_region_tags)}")

    metadata_text = "\n".join(metadata_lines)
    try:
        ts = _slack_service.post_message(channel_id, metadata_text)
        if ts:
            _slack_service.pin_message(channel_id, ts)
    except Exception:
        logger.exception(
            "Failed to post/pin metadata in fallback channel %s", channel_name
        )

    try:
        _slack_service.post_message(
            channel_id,
            ":warning: This channel was created in degraded mode (database unreachable). "
            "The incident has NOT been recorded in Firetower. Details will need to be "
            "backfilled once the database is restored.",
        )
    except Exception:
        logger.exception("Failed to post warning in fallback channel %s", channel_name)

    # Guide message
    guide_message = settings.SLACK.get("INCIDENT_GUIDE_MESSAGE", "")
    if guide_message:
        try:
            _slack_service.post_message(channel_id, guide_message)
        except Exception:
            logger.exception(
                "Failed to post guide message in fallback channel %s", channel_name
            )

    # Invite captain, reporter, and always-invited users
    ids_to_invite: list[str] = []
    if captain_slack_id:
        ids_to_invite.append(captain_slack_id)
    if slack_user_id and slack_user_id not in ids_to_invite:
        ids_to_invite.append(slack_user_id)

    always_invited = settings.SLACK.get("ALWAYS_INVITED_IDS", [])
    for uid in always_invited:
        if uid not in ids_to_invite:
            ids_to_invite.append(uid)

    if ids_to_invite:
        try:
            _slack_service.invite_to_channel(channel_id, ids_to_invite)
        except Exception:
            logger.exception(
                "Failed to invite users to fallback channel %s", channel_name
            )

    # Datadog notebook (skip for private incidents)
    if not is_private:
        try:
            from firetower.integrations.services import DatadogService  # noqa: PLC0415

            dd_service = DatadogService()
            if dd_service.configured:
                notebook_url = dd_service.create_notebook(channel_name, title)
                if notebook_url:
                    _slack_service.add_bookmark(
                        channel_id, "Datadog Notebook", notebook_url
                    )
                    _slack_service.post_message(
                        channel_id, f"Datadog notebook created: {notebook_url}"
                    )
        except Exception:
            logger.exception(
                "Failed to create Datadog notebook for fallback channel %s",
                channel_name,
            )

    # Notion troubleshooting doc (skip for private incidents)
    if not is_private:
        try:
            from firetower.integrations.services.notion import (  # noqa: PLC0415
                NotionService,
            )

            if NotionService.is_troubleshooting_configured():
                notion = NotionService.for_troubleshooting()
                if notion:
                    page = notion.create_troubleshooting_page(channel_name, "")
                    if page and page.get("url"):
                        _slack_service.add_bookmark(
                            channel_id, "Troubleshooting Doc", page["url"]
                        )
                        _slack_service.post_message(
                            channel_id,
                            f"A <{page['url']}|Clinical Troubleshooting document> has been created. "
                            "Please use this to keep track of Symptoms, Hypothesis, and Actions "
                            "as you're investigating this incident.",
                        )
        except Exception:
            logger.exception(
                "Failed to create troubleshooting doc for fallback channel %s",
                channel_name,
            )

    # Status channel (skip for private, only for P0/P1)
    if not is_private and severity in _FALLBACK_PAGEABLE_SEVERITIES:
        try:
            status_channel_name = f"{channel_name}-status"
            status_channel_id = _slack_service.create_channel(
                status_channel_name, is_private=False
            )
            if status_channel_id:
                _slack_service.post_message(
                    status_channel_id,
                    f"This is the status channel for *{channel_name}*.\n"
                    f"For incident response coordination, join <#{channel_id}>.",
                )
                status_invite_ids = list(ids_to_invite)
                for uid in always_invited:
                    if uid not in status_invite_ids:
                        status_invite_ids.append(uid)
                if status_invite_ids:
                    _slack_service.invite_to_channel(
                        status_channel_id, status_invite_ids
                    )
                _slack_service.post_message(
                    channel_id,
                    f"<#{status_channel_id}> has been created for status updates.",
                )
        except Exception:
            logger.exception(
                "Failed to create status channel for fallback channel %s",
                channel_name,
            )

    # Invite oncall users (only for P0/P1)
    if severity in _FALLBACK_PAGEABLE_SEVERITIES:
        try:
            from firetower.incidents.hooks import PAGING_POLICIES  # noqa: PLC0415
            from firetower.integrations.services import (  # noqa: PLC0415
                PagerDutyService,
            )

            pd_config = settings.PAGERDUTY
            if pd_config:
                escalation_policies = pd_config.get("ESCALATION_POLICIES", {})
                pd_service = None
                role_entries: list[tuple[int, int, str]] = []
                users_to_invite: list[tuple[str, str]] = []

                for policy_index, (policy_name, policy_info) in enumerate(
                    PAGING_POLICIES.items()
                ):
                    policy = escalation_policies.get(policy_name)
                    if not policy:
                        continue
                    policy_id = policy.get("id")
                    if not policy_id:
                        continue

                    if pd_service is None:
                        pd_service = PagerDutyService()

                    oncall_users = pd_service.get_oncall_users(policy_id)
                    for oncall_user in oncall_users:
                        email = oncall_user.get("email")
                        escalation_level: int | None = oncall_user.get(
                            "escalation_level"
                        )
                        if (
                            escalation_level is not None
                            and escalation_level > policy_info.max_level
                        ):
                            continue
                        if not email:
                            continue

                        slack_profile = _slack_service.get_user_profile_by_email(email)
                        if not slack_profile or not slack_profile.get("slack_user_id"):
                            continue

                        oncall_slack_id = slack_profile["slack_user_id"]
                        label = policy_info.label
                        if policy_name == "IMOC":
                            role_label = policy_info.page_label
                        elif escalation_level == 1:
                            role_label = f"{label} (Primary)"
                        elif escalation_level == 2:
                            role_label = f"{label} (Secondary)"
                        elif escalation_level is not None:
                            role_label = f"{label} (Level {escalation_level})"
                        else:
                            role_label = label

                        role_entries.append(
                            (
                                policy_index,
                                escalation_level
                                if escalation_level is not None
                                else 999,
                                f"{role_label}: <@{oncall_slack_id}>",
                            )
                        )
                        users_to_invite.append((oncall_slack_id, email))

                if users_to_invite:
                    invite_ids = [sid for sid, _ in users_to_invite]
                    _slack_service.invite_to_channel(channel_id, invite_ids)

                if role_entries:
                    role_entries.sort(key=lambda entry: (entry[0], entry[1]))
                    message = "\n".join(line for _, _, line in role_entries)
                    _slack_service.post_message(channel_id, message)
        except Exception:
            logger.exception(
                "Failed to invite oncall users to fallback channel %s", channel_name
            )

    # PagerDuty paging (only for P0/P1)
    if severity in _FALLBACK_PAGEABLE_SEVERITIES:
        try:
            from firetower.incidents.hooks import PAGING_POLICIES  # noqa: PLC0415
            from firetower.integrations.services import (  # noqa: PLC0415
                PagerDutyService,
            )

            pd_config = settings.PAGERDUTY
            if pd_config:
                escalation_policies = pd_config.get("ESCALATION_POLICIES", {})
                pd_service = None
                channel_url = _slack_service.build_channel_url(channel_id)
                links = [{"href": channel_url, "text": "Slack Channel"}]

                for policy_name, policy_info in PAGING_POLICIES.items():
                    policy = escalation_policies.get(policy_name)
                    if not policy:
                        continue
                    integration_key = policy.get("integration_key")
                    if not integration_key:
                        continue

                    if pd_service is None:
                        pd_service = PagerDutyService()

                    dedup_key = f"firetower-{channel_name}-{policy_name}"
                    page_label = policy_info.page_label
                    summary = f"[{page_label}] [{severity}] {channel_name}: {title}"
                    summary = summary[:1024]

                    success = pd_service.trigger_incident(
                        summary, dedup_key, integration_key, links=links
                    )
                    if not success:
                        _slack_service.post_message(
                            channel_id,
                            f":warning: Failed to page {page_label} via PagerDuty. "
                            "Please manually escalate if needed.",
                        )
        except Exception:
            logger.exception(
                "Failed to page PagerDuty for fallback channel %s", channel_name
            )

    # Post to feed channel (skip for private incidents)
    feed_channel_id = settings.SLACK.get("INCIDENT_FEED_CHANNEL_ID", "")
    if feed_channel_id and not is_private:
        try:
            feed_message = (
                f"A {severity} incident has been created (degraded mode).\n"
                f"{escape_slack_text(title)}"
                f"\n\nFor those involved, please join <#{channel_id}>"
            )
            _slack_service.post_message(feed_channel_id, feed_message)
        except Exception:
            logger.exception(
                "Failed to post feed channel message for fallback channel %s",
                channel_name,
            )

    # DM the user
    try:
        channel_url = _slack_service.build_channel_url(channel_id)
        client.chat_postMessage(
            channel=slack_user_id,
            text=(
                f"An incident channel has been created in degraded mode (database issue).\n"
                f"Slack channel: <#{channel_id}>\n\n"
                "The incident has NOT been recorded in Firetower and will need to be "
                "backfilled once the database is restored."
            ),
        )
    except Exception:
        logger.exception("Failed to DM user about fallback channel %s", channel_name)


def _build_new_incident_modal(channel_id: str = "", user_id: str = "") -> dict:
    severity_options = [
        {
            "text": {"type": "plain_text", "text": sev.label},
            "value": sev.value,
        }
        for sev in IncidentSeverity
    ]
    default_option = {
        "text": {"type": "plain_text", "text": _DEFAULT_SEVERITY.label},
        "value": _DEFAULT_SEVERITY.value,
    }

    blocks = [
        {
            "type": "input",
            "block_id": "captain_block",
            "optional": True,
            "element": {
                "type": "users_select",
                "action_id": "captain_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select incident captain",
                },
                **({"initial_user": user_id} if user_id else {}),
            },
            "label": {"type": "plain_text", "text": "Incident Captain"},
        },
        {
            "type": "input",
            "block_id": "severity_block",
            "element": {
                "type": "static_select",
                "action_id": "severity",
                "placeholder": {"type": "plain_text", "text": "Select severity"},
                "options": severity_options,
                "initial_option": default_option,
            },
            "label": {"type": "plain_text", "text": "Severity"},
        },
        {
            "type": "input",
            "block_id": "title_block",
            "element": {
                "type": "plain_text_input",
                "action_id": "title",
                "placeholder": {"type": "plain_text", "text": "Brief incident title"},
            },
            "label": {"type": "plain_text", "text": "Title"},
        },
        {
            "type": "input",
            "block_id": "description_block",
            "optional": True,
            "element": {
                "type": "plain_text_input",
                "action_id": "description",
                "multiline": True,
                "placeholder": {
                    "type": "plain_text",
                    "text": "What's happening?",
                },
            },
            "label": {"type": "plain_text", "text": "Description"},
        },
        {
            "type": "input",
            "block_id": "impact_summary_block",
            "optional": True,
            "element": {
                "type": "plain_text_input",
                "action_id": "impact_summary",
                "multiline": True,
                "placeholder": {
                    "type": "plain_text",
                    "text": "What is the user/business impact?",
                },
            },
            "label": {"type": "plain_text", "text": "Impact Summary"},
        },
        {
            "type": "input",
            "block_id": "impact_type_block",
            "optional": True,
            "element": {
                "type": "multi_external_select",
                "action_id": "impact_type_tags",
                "min_query_length": 0,
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select impact types",
                },
            },
            "label": {"type": "plain_text", "text": "Impact Type"},
        },
        {
            "type": "input",
            "block_id": "affected_service_block",
            "optional": True,
            "element": {
                "type": "multi_external_select",
                "action_id": "affected_service_tags",
                "min_query_length": 0,
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select affected services",
                },
            },
            "label": {"type": "plain_text", "text": "Affected Service"},
        },
        {
            "type": "input",
            "block_id": "affected_region_block",
            "optional": True,
            "element": {
                "type": "multi_external_select",
                "action_id": "affected_region_tags",
                "min_query_length": 0,
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select affected regions",
                },
            },
            "label": {"type": "plain_text", "text": "Affected Region"},
        },
    ]

    blocks.append(
        {
            "type": "input",
            "block_id": "private_block",
            "optional": True,
            "element": {
                "type": "checkboxes",
                "action_id": "is_private",
                "options": [
                    {
                        "text": {"type": "plain_text", "text": "Private incident"},
                        "value": "private",
                    }
                ],
            },
            "label": {"type": "plain_text", "text": "Visibility"},
        }
    )

    modal = {
        "type": "modal",
        "callback_id": "new_incident_modal",
        "title": {"type": "plain_text", "text": "New Incident"},
        "submit": {"type": "plain_text", "text": "Create"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }
    if channel_id:
        modal["private_metadata"] = channel_id
    return modal


ACTION_ID_TO_TAG_TYPE = {
    "impact_type_tags": TagType.IMPACT_TYPE,
    "affected_service_tags": TagType.AFFECTED_SERVICE,
    "affected_region_tags": TagType.AFFECTED_REGION,
}


def handle_tag_options(ack: Any, payload: dict) -> None:
    action_id = payload.get("action_id", "")
    keyword = payload.get("value", "")

    tag_type = ACTION_ID_TO_TAG_TYPE.get(action_id)
    if not tag_type:
        ack(options=[])
        return

    qs = Tag.objects.filter(type=tag_type)
    if keyword:
        qs = qs.filter(name__icontains=keyword)

    options = [
        {"text": {"type": "plain_text", "text": tag.name}, "value": tag.name}
        for tag in qs.order_by("name")[:100]
    ]
    ack(options=options)


def handle_new_command(ack: Any, body: dict, command: dict, respond: Any) -> None:
    ack()
    trigger_id = body.get("trigger_id")
    if not trigger_id:
        respond("Could not open modal — missing trigger_id.")
        return

    channel_id = body.get("channel_id", "")
    user_id = body.get("user_id", "")

    from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415

    get_bolt_app().client.views_open(
        trigger_id=trigger_id,
        view=_build_new_incident_modal(channel_id=channel_id, user_id=user_id),
    )


def handle_new_incident_submission(
    ack: Any, body: dict, view: dict, client: Any
) -> None:
    values = view.get("state", {}).get("values", {})

    title = values.get("title_block", {}).get("title", {}).get("value", "").strip()
    severity = (
        values.get("severity_block", {})
        .get("severity", {})
        .get("selected_option", {})
        .get("value", _DEFAULT_SEVERITY.value)
    )
    description = (
        values.get("description_block", {}).get("description", {}).get("value") or ""
    )
    impact_summary = (
        values.get("impact_summary_block", {}).get("impact_summary", {}).get("value")
        or ""
    )

    impact_type_selections = (
        values.get("impact_type_block", {})
        .get("impact_type_tags", {})
        .get("selected_options")
        or []
    )
    impact_type_tags = [opt["value"] for opt in impact_type_selections]

    affected_service_selections = (
        values.get("affected_service_block", {})
        .get("affected_service_tags", {})
        .get("selected_options")
        or []
    )
    affected_service_tags = [opt["value"] for opt in affected_service_selections]

    affected_region_selections = (
        values.get("affected_region_block", {})
        .get("affected_region_tags", {})
        .get("selected_options")
        or []
    )
    affected_region_tags = [opt["value"] for opt in affected_region_selections]

    captain_slack_id = (
        values.get("captain_block", {}).get("captain_select", {}).get("selected_user")
    )

    private_selections = (
        values.get("private_block", {}).get("is_private", {}).get("selected_options")
        or []
    )
    is_private = any(opt.get("value") == "private" for opt in private_selections)

    if not title:
        ack(
            response_action="errors",
            errors={"title_block": "This field is required."},
        )
        return

    ack()

    slack_user_id = body.get("user", {}).get("id", "")
    user = get_or_create_user_from_slack_id(slack_user_id)
    if not user:
        client.chat_postMessage(
            channel=slack_user_id,
            text="Could not identify your Firetower account. Please try again or create the incident manually.",
        )
        return

    captain_email = user.email
    if captain_slack_id:
        captain_user = get_or_create_user_from_slack_id(captain_slack_id)
        if captain_user:
            captain_email = captain_user.email

    data = {
        "title": title,
        "severity": severity,
        "description": description,
        "impact_summary": impact_summary,
        "captain": captain_email,
        "reporter": user.email,
        "is_private": is_private,
    }
    if impact_type_tags:
        data["impact_type_tags"] = impact_type_tags
    if affected_service_tags:
        data["affected_service_tags"] = affected_service_tags
    if affected_region_tags:
        data["affected_region_tags"] = affected_region_tags

    serializer = IncidentWriteSerializer(data=data)
    if not serializer.is_valid():
        logger.error("Incident validation failed: %s", serializer.errors)
        client.chat_postMessage(
            channel=slack_user_id,
            text="Something went wrong validating your incident. Please try again.",
        )
        return

    try:
        incident = serializer.save()
    except Exception:
        logger.exception("Failed to create incident from Slack modal")
        form_data = {
            "title": title,
            "severity": severity,
            "description": description,
            "impact_summary": impact_summary,
            "captain_slack_id": captain_slack_id,
            "is_private": is_private,
            "impact_type_tags": impact_type_tags,
            "affected_service_tags": affected_service_tags,
            "affected_region_tags": affected_region_tags,
        }
        _create_fallback_channel(client, slack_user_id, form_data)
        return

    try:
        base_url = settings.FIRETOWER_BASE_URL
        incident_url = f"{base_url}/{incident.incident_number}"
        slack_link = incident.external_links_dict.get("slack", "")

        channel_id = (
            _slack_service.parse_channel_id_from_url(slack_link) if slack_link else None
        )

        dm_message = "The incident has been created, details below.\n\n"
        dm_message += f"Incident: {incident_url}\n"
        if channel_id:
            dm_message += f"Slack channel: <#{channel_id}>"

        client.chat_postMessage(channel=slack_user_id, text=dm_message)

        invoking_channel = view.get("private_metadata", "")
        feed_channel_id = settings.SLACK.get("INCIDENT_FEED_CHANNEL_ID", "")
        if (
            invoking_channel
            and not is_private
            and invoking_channel != slack_user_id
            and invoking_channel != feed_channel_id
        ):
            channel_message = (
                f"A {incident.severity} incident has been created.\n"
                f"<{incident_url}|{incident.incident_number} {escape_slack_text(incident.title)}>"
            )
            if channel_id:
                channel_message += (
                    f"\n\nFor those involved, please join <#{channel_id}>"
                )
            _slack_service.join_channel(invoking_channel)
            client.chat_postMessage(channel=invoking_channel, text=channel_message)
    except Exception:
        logger.exception("Failed to send incident creation notifications")
