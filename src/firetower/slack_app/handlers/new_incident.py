import logging
from typing import Any

from django.conf import settings

from firetower.auth.services import get_or_create_user_from_slack_id
from firetower.incidents.models import IncidentSeverity, Tag, TagType
from firetower.incidents.serializers import IncidentWriteSerializer

logger = logging.getLogger(__name__)


def _build_new_incident_modal() -> dict:
    severity_options = [
        {
            "text": {"type": "plain_text", "text": sev.label},
            "value": sev.value,
        }
        for sev in IncidentSeverity
    ]

    impact_type_options = [
        {"text": {"type": "plain_text", "text": t.name}, "value": t.name}
        for t in Tag.objects.filter(type=TagType.IMPACT_TYPE).order_by("name")
    ]
    affected_service_options = [
        {"text": {"type": "plain_text", "text": t.name}, "value": t.name}
        for t in Tag.objects.filter(type=TagType.AFFECTED_SERVICE).order_by("name")
    ]
    affected_region_options = [
        {"text": {"type": "plain_text", "text": t.name}, "value": t.name}
        for t in Tag.objects.filter(type=TagType.AFFECTED_REGION).order_by("name")
    ]

    blocks = [
        {
            "type": "input",
            "block_id": "severity_block",
            "element": {
                "type": "static_select",
                "action_id": "severity",
                "placeholder": {"type": "plain_text", "text": "Select severity"},
                "options": severity_options,
                "initial_option": {sev["value"]: sev for sev in severity_options}.get(
                    "P2", severity_options[0]
                ),
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
    ]

    if impact_type_options:
        blocks.append(
            {
                "type": "input",
                "block_id": "impact_type_block",
                "optional": True,
                "element": {
                    "type": "multi_static_select",
                    "action_id": "impact_type_tags",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select impact types",
                    },
                    "options": impact_type_options,
                },
                "label": {"type": "plain_text", "text": "Impact Type"},
            }
        )

    if affected_service_options:
        blocks.append(
            {
                "type": "input",
                "block_id": "affected_service_block",
                "optional": True,
                "element": {
                    "type": "multi_static_select",
                    "action_id": "affected_service_tags",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select affected services",
                    },
                    "options": affected_service_options,
                },
                "label": {"type": "plain_text", "text": "Affected Service"},
            }
        )

    if affected_region_options:
        blocks.append(
            {
                "type": "input",
                "block_id": "affected_region_block",
                "optional": True,
                "element": {
                    "type": "multi_static_select",
                    "action_id": "affected_region_tags",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select affected regions",
                    },
                    "options": affected_region_options,
                },
                "label": {"type": "plain_text", "text": "Affected Region"},
            }
        )

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

    return {
        "type": "modal",
        "callback_id": "new_incident_modal",
        "title": {"type": "plain_text", "text": "New Incident"},
        "submit": {"type": "plain_text", "text": "Create"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }


def handle_new_command(ack: Any, body: dict, command: dict, respond: Any) -> None:
    ack()
    trigger_id = body.get("trigger_id")
    if not trigger_id:
        respond("Could not open modal — missing trigger_id.")
        return

    from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415

    get_bolt_app().client.views_open(
        trigger_id=trigger_id, view=_build_new_incident_modal()
    )


def handle_new_incident_submission(
    ack: Any, body: dict, view: dict, client: Any
) -> None:
    values = view.get("state", {}).get("values", {})

    title = values.get("title_block", {}).get("title", {}).get("value", "")
    severity = (
        values.get("severity_block", {})
        .get("severity", {})
        .get("selected_option", {})
        .get("value", "P2")
    )
    description = (
        values.get("description_block", {}).get("description", {}).get("value") or ""
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

    slack_user_id = body.get("user", {}).get("id", "")
    user = get_or_create_user_from_slack_id(slack_user_id)
    if not user:
        ack(
            response_action="errors",
            errors={"title_block": "Could not identify your Firetower account."},
        )
        return

    data = {
        "title": title,
        "severity": severity,
        "description": description,
        "captain": user.email,
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
        errors = {}
        if "title" in serializer.errors:
            errors["title_block"] = str(serializer.errors["title"][0])
        if "severity" in serializer.errors:
            errors["severity_block"] = str(serializer.errors["severity"][0])
        if not errors:
            first_key = next(iter(serializer.errors))
            errors["title_block"] = str(serializer.errors[first_key][0])
        ack(response_action="errors", errors=errors)
        return

    ack()

    try:
        incident = serializer.save()
    except Exception:
        logger.exception("Failed to create incident from Slack modal")
        client.chat_postMessage(
            channel=slack_user_id,
            text=(
                "Something went wrong creating your incident. "
                "Please create it manually in Firetower and create a Slack channel, "
                "then let #team-sre know."
            ),
        )
        return

    base_url = settings.FIRETOWER_BASE_URL
    incident_url = f"{base_url}/incidents/{incident.incident_number}"
    slack_link = incident.external_links_dict.get("slack", "")

    message = f"*{incident.incident_number}: {incident.title}* created!\n<{incident_url}|View in Firetower>"
    if slack_link:
        message += f"\n<{slack_link}|Slack channel>"

    client.chat_postMessage(channel=slack_user_id, text=message)
