import logging
from typing import Any

from firetower.auth.models import ExternalProfileType
from firetower.auth.services import get_or_create_user_from_slack_id
from firetower.incidents.models import Incident, IncidentSeverity, IncidentStatus
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.slack_app.handlers.utils import (
    get_incident_from_channel,
    parse_incident_form_values,
)

logger = logging.getLogger(__name__)


def _build_resolved_modal(incident: Incident, channel_id: str) -> dict:
    severity_options = [
        {
            "text": {"type": "plain_text", "text": sev.label},
            "value": sev.value,
        }
        for sev in IncidentSeverity
    ]
    current_severity = IncidentSeverity(incident.severity)
    current_severity_option = {
        "text": {"type": "plain_text", "text": current_severity.label},
        "value": current_severity.value,
    }

    captain_element: dict[str, Any] = {
        "type": "users_select",
        "action_id": "captain_select",
        "placeholder": {"type": "plain_text", "text": "Select incident captain"},
    }
    if incident.captain:
        slack_profile = incident.captain.external_profiles.filter(
            type=ExternalProfileType.SLACK
        ).first()
        if slack_profile:
            captain_element["initial_user"] = slack_profile.external_id

    title_element: dict[str, Any] = {
        "type": "plain_text_input",
        "action_id": "title",
        "placeholder": {"type": "plain_text", "text": "Brief incident title"},
        "initial_value": incident.title or "",
    }

    description_element: dict[str, Any] = {
        "type": "plain_text_input",
        "action_id": "description",
        "multiline": True,
        "placeholder": {"type": "plain_text", "text": "What's happening?"},
    }
    if incident.description:
        description_element["initial_value"] = incident.description

    impact_summary_element: dict[str, Any] = {
        "type": "plain_text_input",
        "action_id": "impact_summary",
        "multiline": True,
        "placeholder": {
            "type": "plain_text",
            "text": "What is the user/business impact?",
        },
    }
    if incident.impact_summary:
        impact_summary_element["initial_value"] = incident.impact_summary

    impact_type_initial = [
        {"text": {"type": "plain_text", "text": name}, "value": name}
        for name in incident.impact_type_tag_names
    ]
    impact_type_element: dict[str, Any] = {
        "type": "multi_external_select",
        "action_id": "impact_type_tags",
        "min_query_length": 0,
        "placeholder": {"type": "plain_text", "text": "Select impact types"},
    }
    if impact_type_initial:
        impact_type_element["initial_options"] = impact_type_initial

    affected_service_initial = [
        {"text": {"type": "plain_text", "text": name}, "value": name}
        for name in incident.affected_service_tag_names
    ]
    affected_service_element: dict[str, Any] = {
        "type": "multi_external_select",
        "action_id": "affected_service_tags",
        "min_query_length": 0,
        "placeholder": {"type": "plain_text", "text": "Select affected services"},
    }
    if affected_service_initial:
        affected_service_element["initial_options"] = affected_service_initial

    affected_region_initial = [
        {"text": {"type": "plain_text", "text": name}, "value": name}
        for name in incident.affected_region_tag_names
    ]
    affected_region_element: dict[str, Any] = {
        "type": "multi_external_select",
        "action_id": "affected_region_tags",
        "min_query_length": 0,
        "placeholder": {"type": "plain_text", "text": "Select affected regions"},
    }
    if affected_region_initial:
        affected_region_element["initial_options"] = affected_region_initial

    return {
        "type": "modal",
        "callback_id": "resolved_incident_modal",
        "private_metadata": channel_id,
        "title": {"type": "plain_text", "text": incident.incident_number},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "This incident has been contained! Please confirm the details below.",
                },
            },
            {
                "type": "input",
                "block_id": "captain_block",
                "element": captain_element,
                "label": {"type": "plain_text", "text": "Incident Captain"},
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "The incident captain is responsible for driving the postmortem.",
                    }
                ],
            },
            {
                "type": "input",
                "block_id": "severity_block",
                "element": {
                    "type": "static_select",
                    "action_id": "severity_select",
                    "options": severity_options,
                    "initial_option": current_severity_option,
                },
                "label": {"type": "plain_text", "text": "Severity"},
            },
            {
                "type": "input",
                "block_id": "title_block",
                "element": title_element,
                "label": {"type": "plain_text", "text": "Title"},
            },
            {
                "type": "input",
                "block_id": "description_block",
                "optional": True,
                "element": description_element,
                "label": {"type": "plain_text", "text": "Description"},
            },
            {
                "type": "input",
                "block_id": "impact_summary_block",
                "optional": True,
                "element": impact_summary_element,
                "label": {"type": "plain_text", "text": "Impact Summary"},
            },
            {
                "type": "input",
                "block_id": "impact_type_block",
                "optional": True,
                "element": impact_type_element,
                "label": {"type": "plain_text", "text": "Impact Type"},
            },
            {
                "type": "input",
                "block_id": "affected_service_block",
                "optional": True,
                "element": affected_service_element,
                "label": {"type": "plain_text", "text": "Affected Service"},
            },
            {
                "type": "input",
                "block_id": "affected_region_block",
                "optional": True,
                "element": affected_region_element,
                "label": {"type": "plain_text", "text": "Affected Region"},
            },
        ],
    }


def handle_resolved_command(ack: Any, body: dict, command: dict, respond: Any) -> None:
    ack()
    channel_id = body.get("channel_id", "")
    incident = get_incident_from_channel(channel_id)
    if not incident:
        respond("Could not find an incident associated with this channel.")
        return

    trigger_id = body.get("trigger_id")
    if not trigger_id:
        respond("Could not open modal — missing trigger_id.")
        return

    from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415

    get_bolt_app().client.views_open(
        trigger_id=trigger_id,
        view=_build_resolved_modal(incident, channel_id),
    )


def handle_resolved_submission(ack: Any, body: dict, view: dict, client: Any) -> None:
    form = parse_incident_form_values(view)
    channel_id = view.get("private_metadata", "")

    values = view.get("state", {}).get("values", {})

    # The resolved modal uses "severity_select" as action_id (not "severity")
    severity = (
        values.get("severity_block", {})
        .get("severity_select", {})
        .get("selected_option", {})
        .get("value", "")
    ) or form["severity"]

    captain_slack_id = form["captain_slack_id"]

    if not captain_slack_id:
        ack(
            response_action="errors",
            errors={"captain_block": "An incident captain is required."},
        )
        return

    if not form["title"]:
        ack(
            response_action="errors",
            errors={"title_block": "This field is required."},
        )
        return

    ack()

    incident = get_incident_from_channel(channel_id)
    if not incident:
        logger.error("Resolved submission: no incident for channel %s", channel_id)
        return

    captain_user = get_or_create_user_from_slack_id(captain_slack_id)
    if not captain_user:
        logger.error(
            "Could not resolve Slack user %s to a Firetower user", captain_slack_id
        )
        client.chat_postMessage(
            channel=channel_id,
            text="Failed to resolve the selected captain to a Firetower user.",
        )
        return

    if severity in ("P0", "P1", "P2"):
        target_status = IncidentStatus.POSTMORTEM
    else:
        target_status = IncidentStatus.DONE

    data: dict[str, Any] = {
        "status": target_status,
        "severity": severity,
        "captain": captain_user.email,
        "title": form["title"],
        "description": form["description"],
        "impact_summary": form["impact_summary"],
        "impact_type_tags": form["impact_type_tags"],
        "affected_service_tags": form["affected_service_tags"],
        "affected_region_tags": form["affected_region_tags"],
    }

    serializer = IncidentWriteSerializer(instance=incident, data=data, partial=True)
    if not serializer.is_valid():
        logger.error("Resolved update failed: %s", serializer.errors)
        client.chat_postMessage(
            channel=channel_id,
            text=f"Failed to resolve incident: {serializer.errors}",
        )
        return
    serializer.save()

    client.chat_postMessage(
        channel=channel_id,
        text=(
            f"*{incident.incident_number} marked as {target_status}*\n"
            f"Severity: {severity} | Captain: {captain_user.get_full_name()}"
        ),
    )

    # TODO: Postmortem doc generation will be added in RELENG-466 (Notion integration)
