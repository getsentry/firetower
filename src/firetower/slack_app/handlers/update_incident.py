import logging
from typing import Any

from firetower.incidents.models import Incident, IncidentSeverity
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)


def _build_update_incident_modal(incident: Incident, channel_id: str) -> dict:
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

    impact_type_initial = [
        {"text": {"type": "plain_text", "text": name}, "value": name}
        for name in incident.impact_type_tag_names
    ]
    affected_service_initial = [
        {"text": {"type": "plain_text", "text": name}, "value": name}
        for name in incident.affected_service_tag_names
    ]
    affected_region_initial = [
        {"text": {"type": "plain_text", "text": name}, "value": name}
        for name in incident.affected_region_tag_names
    ]

    severity_element: dict[str, Any] = {
        "type": "static_select",
        "action_id": "severity",
        "placeholder": {"type": "plain_text", "text": "Select severity"},
        "options": severity_options,
        "initial_option": current_severity_option,
    }

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

    impact_type_element: dict[str, Any] = {
        "type": "multi_external_select",
        "action_id": "impact_type_tags",
        "min_query_length": 0,
        "placeholder": {"type": "plain_text", "text": "Select impact types"},
    }
    if impact_type_initial:
        impact_type_element["initial_options"] = impact_type_initial

    affected_service_element: dict[str, Any] = {
        "type": "multi_external_select",
        "action_id": "affected_service_tags",
        "min_query_length": 0,
        "placeholder": {"type": "plain_text", "text": "Select affected services"},
    }
    if affected_service_initial:
        affected_service_element["initial_options"] = affected_service_initial

    affected_region_element: dict[str, Any] = {
        "type": "multi_external_select",
        "action_id": "affected_region_tags",
        "min_query_length": 0,
        "placeholder": {"type": "plain_text", "text": "Select affected regions"},
    }
    if affected_region_initial:
        affected_region_element["initial_options"] = affected_region_initial

    private_element: dict[str, Any] = {
        "type": "checkboxes",
        "action_id": "is_private",
        "options": [
            {
                "text": {"type": "plain_text", "text": "Private incident"},
                "value": "private",
            }
        ],
    }
    if incident.is_private:
        private_element["initial_options"] = [
            {
                "text": {"type": "plain_text", "text": "Private incident"},
                "value": "private",
            }
        ]

    blocks = [
        {
            "type": "input",
            "block_id": "severity_block",
            "element": severity_element,
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
        {
            "type": "input",
            "block_id": "private_block",
            "optional": True,
            "element": private_element,
            "label": {"type": "plain_text", "text": "Visibility"},
        },
    ]

    return {
        "type": "modal",
        "callback_id": "update_incident_modal",
        "title": {"type": "plain_text", "text": incident.incident_number},
        "submit": {"type": "plain_text", "text": "Update"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "private_metadata": channel_id,
        "blocks": blocks,
    }


def handle_update_command(ack: Any, body: dict, command: dict, respond: Any) -> None:
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
        view=_build_update_incident_modal(incident, channel_id),
    )


def handle_update_incident_submission(
    ack: Any, body: dict, view: dict, client: Any
) -> None:
    values = view.get("state", {}).get("values", {})
    channel_id = view.get("private_metadata", "")

    title = values.get("title_block", {}).get("title", {}).get("value", "").strip()
    severity = (
        values.get("severity_block", {})
        .get("severity", {})
        .get("selected_option", {})
        .get("value")
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

    incident = get_incident_from_channel(channel_id)
    if not incident:
        logger.error("Update submission: no incident for channel %s", channel_id)
        return

    data: dict[str, Any] = {
        "title": title,
        "severity": severity,
        "description": description,
        "impact_summary": impact_summary,
        "is_private": is_private,
        "impact_type_tags": impact_type_tags,
        "affected_service_tags": affected_service_tags,
        "affected_region_tags": affected_region_tags,
    }

    serializer = IncidentWriteSerializer(instance=incident, data=data, partial=True)
    if not serializer.is_valid():
        logger.error("Incident update validation failed: %s", serializer.errors)
        client.chat_postMessage(
            channel=channel_id,
            text=f"Failed to update incident: {serializer.errors}",
        )
        return

    try:
        serializer.save()
    except Exception:
        logger.exception("Failed to update incident from Slack modal")
        client.chat_postMessage(
            channel=channel_id,
            text="Something went wrong updating the incident. Please try again.",
        )
        return

    client.chat_postMessage(
        channel=channel_id,
        text=f"*{incident.incident_number}* has been updated.",
    )
