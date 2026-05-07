from typing import Any

from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
)

_DEFAULT_SEVERITY = IncidentSeverity.P3


def get_incident_from_channel(channel_id: str) -> Incident | None:
    link = (
        ExternalLink.objects.filter(
            type=ExternalLinkType.SLACK,
            url__endswith=f"/archives/{channel_id}",
        )
        .select_related("incident")
        .first()
    )
    if link:
        return link.incident
    return None


def build_incident_form_blocks(user_id: str = "") -> list[dict[str, Any]]:
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

    return [
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


def parse_incident_form_values(view: dict) -> dict[str, Any]:
    values = view.get("state", {}).get("values", {})

    title = values.get("title_block", {}).get("title", {}).get("value", "").strip()
    selected_option = (
        values.get("severity_block", {}).get("severity", {}).get("selected_option")
    )
    severity = selected_option.get("value") if selected_option else None
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

    return {
        "title": title,
        "severity": severity,
        "description": description,
        "impact_summary": impact_summary,
        "impact_type_tags": impact_type_tags,
        "affected_service_tags": affected_service_tags,
        "affected_region_tags": affected_region_tags,
        "captain_slack_id": captain_slack_id,
    }
