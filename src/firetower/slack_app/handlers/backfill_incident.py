import logging
import re
from typing import Any

from django.conf import settings

from firetower.auth.services import get_or_create_user_from_slack_id
from firetower.incidents.hooks import _build_channel_topic
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    IncidentSeverity,
)
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.incidents.services import sync_incident_participants_from_slack
from firetower.integrations.services import SlackService

logger = logging.getLogger(__name__)
_slack_service = SlackService()

_DEFAULT_SEVERITY = IncidentSeverity.P3


def _expected_channel_name(incident_id: int) -> str:
    project_key = settings.PROJECT_KEY
    return f"{project_key}-{incident_id}".lower()


def _parse_channel_id_from_args(args: str) -> str | None:
    match = re.search(r"<#(C[A-Z0-9]+)\|", args)
    if match:
        return match.group(1)
    match = re.search(r"(C[A-Z0-9]+)", args)
    if match:
        return match.group(1)
    return None


def _build_backfill_modal(channel_id: str, user_id: str = "") -> dict:
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

    modal = {
        "type": "modal",
        "callback_id": "backfill_incident_modal",
        "title": {"type": "plain_text", "text": "Backfill Incident"},
        "submit": {"type": "plain_text", "text": "Backfill"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
        "private_metadata": channel_id,
    }
    return modal


def handle_backfill_command(ack: Any, body: dict, command: dict, respond: Any) -> None:
    ack()

    raw_text = (body.get("text") or "").strip()
    parts = raw_text.split(None, 1)
    args = parts[1] if len(parts) > 1 else ""

    channel_id = _parse_channel_id_from_args(args) if args else None
    if not channel_id:
        channel_id = body.get("channel_id", "")

    if not channel_id:
        respond(
            "Could not determine channel. Run this from an incident channel or specify one: `/ft backfill #channel`"
        )
        return

    channel_info = _slack_service.get_channel_info(channel_id)
    expected_prefix = f"{settings.PROJECT_KEY}-".lower()
    if not channel_info or not channel_info["name"].startswith(expected_prefix):
        respond(
            f"Backfill is only allowed on incident channels (name must start with `{expected_prefix}`)."
        )
        return

    existing_link = ExternalLink.objects.filter(
        type=ExternalLinkType.SLACK,
        url__endswith=f"/archives/{channel_id}",
    ).first()
    if existing_link:
        respond(
            f"This channel is already linked to {existing_link.incident.incident_number}."
        )
        return

    trigger_id = body.get("trigger_id")
    if not trigger_id:
        respond("Could not open modal -- missing trigger_id.")
        return

    user_id = body.get("user_id", "")

    from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415

    get_bolt_app().client.views_open(
        trigger_id=trigger_id,
        view=_build_backfill_modal(channel_id=channel_id, user_id=user_id),
    )


def handle_backfill_submission(ack: Any, body: dict, view: dict, client: Any) -> None:
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

    if not title:
        ack(
            response_action="errors",
            errors={"title_block": "This field is required."},
        )
        return

    ack()

    channel_id = view.get("private_metadata", "")
    slack_user_id = body.get("user", {}).get("id", "")

    user = get_or_create_user_from_slack_id(slack_user_id)
    if not user:
        client.chat_postMessage(
            channel=slack_user_id,
            text="Could not identify your Firetower account. Please try again.",
        )
        return

    captain_email = user.email
    if captain_slack_id:
        captain_user = get_or_create_user_from_slack_id(captain_slack_id)
        if captain_user:
            captain_email = captain_user.email

    channel_url = _slack_service.build_channel_url(channel_id)
    channel_info = _slack_service.get_channel_info(channel_id)
    is_private = bool(channel_info and channel_info.get("is_private"))

    data: dict[str, Any] = {
        "title": title,
        "severity": severity,
        "description": description,
        "impact_summary": impact_summary,
        "captain": captain_email,
        "reporter": user.email,
        "is_private": is_private,
        "external_links": {"slack": channel_url},
    }
    if impact_type_tags:
        data["impact_type_tags"] = impact_type_tags
    if affected_service_tags:
        data["affected_service_tags"] = affected_service_tags
    if affected_region_tags:
        data["affected_region_tags"] = affected_region_tags

    serializer = IncidentWriteSerializer(data=data, context={"skip_hooks": True})
    if not serializer.is_valid():
        logger.error("Backfill incident validation failed: %s", serializer.errors)
        client.chat_postMessage(
            channel=slack_user_id,
            text="Something went wrong validating the incident. Please try again.",
        )
        return

    try:
        incident = serializer.save()
    except Exception:
        logger.exception("Failed to create backfill incident from Slack modal")
        client.chat_postMessage(
            channel=slack_user_id,
            text="Something went wrong creating the backfill incident. Please try again.",
        )
        return

    joined = _slack_service.join_channel(channel_id)
    if not joined:
        base_url = settings.FIRETOWER_BASE_URL
        incident_url = f"{base_url}/{incident.incident_number}"
        client.chat_postMessage(
            channel=slack_user_id,
            text=(
                f"Backfill incident created: {incident_url}\n"
                f"However, the bot could not join <#{channel_id}>. "
                f"Please invite the bot to the channel for topic/bookmark setup."
            ),
        )
        return

    expected_name = _expected_channel_name(incident.id)
    channel_info = _slack_service.get_channel_info(channel_id)
    if channel_info and channel_info["name"] != expected_name:
        renamed = _slack_service.rename_channel(channel_id, expected_name)
        if not renamed:
            logger.warning(
                "Failed to rename channel %s to %s for incident %s",
                channel_id,
                expected_name,
                incident.id,
            )

    _slack_service.set_channel_topic(channel_id, _build_channel_topic(incident))
    base_url = settings.FIRETOWER_BASE_URL
    incident_url = f"{base_url}/{incident.incident_number}"
    _slack_service.add_bookmark(channel_id, "Firetower Incident", incident_url)

    try:
        sync_incident_participants_from_slack(incident, force=True)
    except Exception:
        logger.exception(
            "Failed to sync participants for backfill incident %s", incident.id
        )

    dm_message = (
        f"Backfill incident created: {incident_url}\nSlack channel: <#{channel_id}>"
    )
    client.chat_postMessage(channel=slack_user_id, text=dm_message)
