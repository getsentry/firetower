from typing import Any

from django.conf import settings

from firetower.auth.models import ExternalProfileType
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    ServiceTier,
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
            "block_id": "impact_summary_block",
            "optional": True,
            "element": {
                "type": "plain_text_input",
                "action_id": "impact_summary",
                "multiline": True,
                "placeholder": {
                    "type": "plain_text",
                    "text": "How is this affecting users?",
                },
            },
            "label": {"type": "plain_text", "text": "Impact Summary"},
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
    ]


def parse_incident_form_values(view: dict) -> dict[str, Any]:
    values = view.get("state", {}).get("values", {})

    title = values.get("title_block", {}).get("title", {}).get("value", "").strip()
    severity_block = values.get("severity_block", {})
    selected_option = severity_block.get("severity", {}).get(
        "selected_option"
    ) or severity_block.get("severity_select", {}).get("selected_option")
    severity = selected_option.get("value") if selected_option else None
    service_tier_option = (
        values.get("service_tier_block", {})
        .get("service_tier_select", {})
        .get("selected_option")
    )
    service_tier = service_tier_option.get("value") if service_tier_option else None
    description = (
        values.get("description_block", {}).get("description", {}).get("value") or ""
    ).strip()
    impact_summary = (
        values.get("impact_summary_block", {}).get("impact_summary", {}).get("value")
        or ""
    ).strip()

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
        "service_tier": service_tier,
        "description": description,
        "impact_summary": impact_summary,
        "impact_type_tags": impact_type_tags,
        "affected_service_tags": affected_service_tags,
        "affected_region_tags": affected_region_tags,
        "captain_slack_id": captain_slack_id,
    }


def build_incident_lifecycle_modal(
    incident: Incident,
    channel_id: str,
    title_text: str,
    callback_id: str,
    intro_text: str,
) -> dict[str, Any]:
    """Build the shared 9-field modal used by /inc mitigated and /inc resolved.

    Fields are pre-filled from `incident`. All nine fields (captain, severity,
    title, impact_summary, description, impact_type, service_tier,
    affected_service, affected_region) are required by Slack defaults.
    """
    severity_options = [
        {"text": {"type": "plain_text", "text": sev.label}, "value": sev.value}
        for sev in IncidentSeverity
    ]
    current_severity = IncidentSeverity(incident.severity)
    current_severity_option = {
        "text": {"type": "plain_text", "text": current_severity.label},
        "value": current_severity.value,
    }

    service_tier_options = [
        {"text": {"type": "plain_text", "text": tier.label}, "value": tier.value}
        for tier in ServiceTier
    ]

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
        "placeholder": {
            "type": "plain_text",
            "text": "Additional relevant information",
        },
    }
    if incident.description:
        description_element["initial_value"] = incident.description

    impact_summary_element: dict[str, Any] = {
        "type": "plain_text_input",
        "action_id": "impact_summary",
        "multiline": True,
        "placeholder": {"type": "plain_text", "text": "How is this affecting users?"},
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
        "placeholder": {"type": "plain_text", "text": "Type"},
    }
    if impact_type_initial:
        impact_type_element["initial_options"] = impact_type_initial

    service_tier_element: dict[str, Any] = {
        "type": "static_select",
        "action_id": "service_tier_select",
        "placeholder": {"type": "plain_text", "text": "Select service tier"},
        "options": service_tier_options,
    }
    if incident.service_tier:
        current_tier = ServiceTier(incident.service_tier)
        service_tier_element["initial_option"] = {
            "text": {"type": "plain_text", "text": current_tier.label},
            "value": current_tier.value,
        }

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

    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": intro_text},
        },
        {
            "type": "input",
            "block_id": "captain_block",
            "element": captain_element,
            "label": {"type": "plain_text", "text": "Incident Captain"},
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
            "block_id": "impact_summary_block",
            "element": impact_summary_element,
            "label": {"type": "plain_text", "text": "Impact Summary"},
        },
        {
            "type": "input",
            "block_id": "description_block",
            "element": description_element,
            "label": {"type": "plain_text", "text": "Description"},
        },
        {
            "type": "input",
            "block_id": "impact_type_block",
            "element": impact_type_element,
            "label": {"type": "plain_text", "text": "Type of impact"},
        },
        {
            "type": "input",
            "block_id": "service_tier_block",
            "element": service_tier_element,
            "label": {"type": "plain_text", "text": "Service Tier"},
        },
    ]

    service_registry_url = getattr(settings, "SERVICE_REGISTRY_URL", None)
    if service_registry_url:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"<{service_registry_url}|Service Registry>",
                    }
                ],
            }
        )

    incident_url = f"{settings.FIRETOWER_BASE_URL}/{incident.incident_number}"
    blocks.extend(
        [
            {
                "type": "input",
                "block_id": "affected_service_block",
                "element": affected_service_element,
                "label": {"type": "plain_text", "text": "Affected Services"},
            },
            {
                "type": "input",
                "block_id": "affected_region_block",
                "element": affected_region_element,
                "label": {"type": "plain_text", "text": "Affected Regions"},
            },
            # TODO(RELENG-768): drop this hint once inline tag creation
            # ("+ Create 'X'" synthetic option) lands for service/region.
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Missing a service or region? Add it from the <{incident_url}|incident page>.",
                    }
                ],
            },
        ]
    )

    return {
        "type": "modal",
        "callback_id": callback_id,
        "private_metadata": channel_id,
        "title": {"type": "plain_text", "text": title_text[:24]},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }


def validate_lifecycle_form(form: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not form["captain_slack_id"]:
        errors["captain_block"] = "An incident captain is required."
    if not form["severity"]:
        errors["severity_block"] = "Severity is required."
    if not form["title"]:
        errors["title_block"] = "This field is required."
    if not form["description"]:
        errors["description_block"] = "Description is required."
    if not form["impact_summary"]:
        errors["impact_summary_block"] = "Impact summary is required."
    if not form["impact_type_tags"]:
        errors["impact_type_block"] = "Select at least one impact type."
    if not form["service_tier"]:
        errors["service_tier_block"] = "Service tier is required."
    if not form["affected_service_tags"]:
        errors["affected_service_block"] = "Select at least one affected service."
    if not form["affected_region_tags"]:
        errors["affected_region_block"] = "Select at least one affected region."
    return errors


def build_incident_update_data(
    form: dict[str, Any], status: IncidentStatus, captain_email: str
) -> dict[str, Any]:
    return {
        "status": status,
        "severity": form["severity"],
        "service_tier": form["service_tier"],
        "captain": captain_email,
        "title": form["title"],
        "description": form["description"],
        "impact_summary": form["impact_summary"],
        "impact_type_tags": form["impact_type_tags"],
        "affected_service_tags": form["affected_service_tags"],
        "affected_region_tags": form["affected_region_tags"],
    }
