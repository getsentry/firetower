import logging
from typing import Any

import requests

from firetower.incidents.models import ExternalLink, ExternalLinkType
from firetower.integrations.services.statuspage import (
    COMPONENT_STATUS_OPTIONS,
    DEFAULT_MESSAGES,
    IMPACT_OPTIONS,
    SEVERITY_TO_IMPACT,
    STATUS_OPTIONS,
    StatuspageService,
)
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)

COMPONENT_BLOCK_PREFIX = "component_"


def _build_statuspage_modal(
    channel_id: str,
    incident_title: str,
    incident_severity: str,
    statuspage_incident: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status_options = [
        {"text": {"type": "plain_text", "text": label}, "value": value}
        for value, label in STATUS_OPTIONS
    ]

    impact_options = [
        {"text": {"type": "plain_text", "text": label}, "value": value}
        for value, label in IMPACT_OPTIONS
    ]

    component_status_options = [
        {"text": {"type": "plain_text", "text": label}, "value": value}
        for value, label in COMPONENT_STATUS_OPTIONS
    ]

    default_component_option = component_status_options[0]

    is_update = statuspage_incident is not None
    latest_status = "investigating"
    default_impact = SEVERITY_TO_IMPACT.get(incident_severity, "major")
    affected_components: dict[str, str] = {}

    if statuspage_incident:
        incident_updates = sorted(
            statuspage_incident.get("incident_updates", []),
            key=lambda x: x["created_at"],
            reverse=True,
        )
        if incident_updates:
            latest_status = incident_updates[0]["status"]
            for update in incident_updates:
                for component in update.get("affected_components") or []:
                    component_id = component["id"]
                    if component_id not in affected_components:
                        affected_components[component_id] = component["new_status"]
        default_impact = statuspage_incident.get("impact", default_impact)

    initial_status = next(
        (opt for opt in status_options if opt["value"] == latest_status),
        status_options[0],
    )
    initial_impact = next(
        (opt for opt in impact_options if opt["value"] == default_impact),
        next(
            (opt for opt in impact_options if opt["value"] == "major"),
            impact_options[0],
        ),
    )

    blocks: list[dict[str, Any]] = []

    blocks.append(
        {
            "type": "input",
            "block_id": "status_block",
            "element": {
                "type": "static_select",
                "action_id": "status_select",
                "options": status_options,
                "initial_option": initial_status,
            },
            "label": {"type": "plain_text", "text": "Status"},
        }
    )

    if statuspage_incident is not None:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Title:* {statuspage_incident['name']}",
                },
            }
        )
    else:
        blocks.append(
            {
                "type": "input",
                "block_id": "title_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "title_input",
                    "initial_value": incident_title,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Enter a descriptive title for the customer",
                    },
                },
                "label": {"type": "plain_text", "text": "Title"},
            }
        )

    blocks.append(
        {
            "type": "input",
            "block_id": "message_block",
            "element": {
                "type": "plain_text_input",
                "action_id": "message_input",
                "multiline": True,
                "placeholder": {
                    "type": "plain_text",
                    "text": DEFAULT_MESSAGES.get(latest_status, ""),
                },
            },
            "label": {"type": "plain_text", "text": "Message"},
        }
    )

    if not is_update:
        blocks.append(
            {
                "type": "input",
                "block_id": "impact_block",
                "element": {
                    "type": "static_select",
                    "action_id": "impact_select",
                    "options": impact_options,
                    "initial_option": initial_impact,
                },
                "label": {"type": "plain_text", "text": "Impact"},
            }
        )

    service = StatuspageService()
    if service.configured:
        try:
            top_level, children_map = service.get_components()
        except requests.RequestException:
            logger.exception("Failed to fetch statuspage components")
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            ":warning: Could not load Statuspage components. "
                            "You can still submit, but component statuses "
                            "won't be updated."
                        ),
                    },
                }
            )
        else:
            parent_ids = set(children_map.keys())
            sorted_top = sorted(top_level, key=lambda x: x.get("position", 0))

            non_parents = [c for c in sorted_top if c["id"] not in parent_ids]
            if non_parents:
                blocks.append({"type": "divider"})
            for component in non_parents:
                current_impact = affected_components.get(component["id"], "operational")
                initial_component_option = next(
                    (
                        opt
                        for opt in component_status_options
                        if opt["value"] == current_impact
                    ),
                    default_component_option,
                )
                blocks.append(
                    {
                        "type": "section",
                        "block_id": f"{COMPONENT_BLOCK_PREFIX}{component['id']}",
                        "text": {"type": "mrkdwn", "text": f"*{component['name']}*"},
                        "accessory": {
                            "type": "static_select",
                            "action_id": "component_impact_select",
                            "options": component_status_options,
                            "initial_option": initial_component_option,
                        },
                    }
                )

            for parent in sorted_top:
                if parent["id"] not in parent_ids:
                    continue
                blocks.append(
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": parent["name"],
                        },
                    }
                )
                children = sorted(
                    children_map.get(parent["id"], []),
                    key=lambda x: x.get("position", 0),
                )
                for child in children:
                    current_impact = affected_components.get(child["id"], "operational")
                    initial_component_option = next(
                        (
                            opt
                            for opt in component_status_options
                            if opt["value"] == current_impact
                        ),
                        default_component_option,
                    )
                    blocks.append(
                        {
                            "type": "section",
                            "block_id": f"{COMPONENT_BLOCK_PREFIX}{child['id']}",
                            "text": {"type": "mrkdwn", "text": f"*{child['name']}*"},
                            "accessory": {
                                "type": "static_select",
                                "action_id": "component_impact_select",
                                "options": component_status_options,
                                "initial_option": initial_component_option,
                            },
                        }
                    )

    return {
        "type": "modal",
        "callback_id": "statuspage_modal",
        "private_metadata": channel_id,
        "title": {
            "type": "plain_text",
            "text": "Update Statuspage" if is_update else "New Statuspage Post",
        },
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }


def handle_statuspage_command(
    ack: Any, body: dict, command: dict, respond: Any
) -> None:
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

    service = StatuspageService()
    if not service.configured:
        respond("Statuspage is not configured.")
        return

    statuspage_incident = None
    statuspage_link = incident.external_links.filter(
        type=ExternalLinkType.STATUSPAGE
    ).first()

    if statuspage_link:
        sp_id = service.extract_incident_id_from_url(statuspage_link.url)
        if sp_id:
            try:
                statuspage_incident = service.get_incident(sp_id)
            except requests.RequestException:
                logger.exception(
                    "Failed to fetch existing statuspage incident %s", sp_id
                )
                respond(
                    "Could not reach Statuspage to load the existing post. "
                    "Please try again in a moment."
                )
                return

    from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415

    get_bolt_app().client.views_open(
        trigger_id=trigger_id,
        view=_build_statuspage_modal(
            channel_id=channel_id,
            incident_title=incident.title,
            incident_severity=incident.severity,
            statuspage_incident=statuspage_incident,
        ),
    )


def handle_statuspage_submission(ack: Any, body: dict, view: dict, client: Any) -> None:
    values = view.get("state", {}).get("values", {})
    channel_id = view.get("private_metadata", "")

    message = values.get("message_block", {}).get("message_input", {}).get("value", "")
    if not message:
        ack(
            response_action="errors",
            errors={"message_block": "Message is required."},
        )
        return

    service = StatuspageService()
    if not service.configured:
        ack()
        channel_id_for_msg = view.get("private_metadata", "")
        if channel_id_for_msg:
            client.chat_postMessage(
                channel=channel_id_for_msg,
                text=(
                    "Statuspage is not configured. Please contact your administrator."
                ),
            )
        return

    status = (
        values.get("status_block", {})
        .get("status_select", {})
        .get("selected_option", {})
        .get("value", "investigating")
    )
    title = values.get("title_block", {}).get("title_input", {}).get("value", "")
    impact = (
        values.get("impact_block", {})
        .get("impact_select", {})
        .get("selected_option", {})
        .get("value", "major")
    )

    ack()

    incident = get_incident_from_channel(channel_id)
    if not incident:
        logger.error("Statuspage submission: no incident for channel %s", channel_id)
        if channel_id:
            client.chat_postMessage(
                channel=channel_id,
                text=(
                    "Could not find an incident associated with this channel — "
                    "the Statuspage submission was not processed."
                ),
            )
        return

    components: dict[str, str] = {}
    for block_id, block_content in values.items():
        if not block_id.startswith(COMPONENT_BLOCK_PREFIX):
            continue
        select_data = block_content.get("component_impact_select", {})
        if select_data:
            selected = select_data.get("selected_option", {})
            if selected:
                component_id = block_id[len(COMPONENT_BLOCK_PREFIX) :]
                components[component_id] = selected.get("value", "operational")

    try:
        statuspage_link, created = ExternalLink.objects.get_or_create(
            incident=incident,
            type=ExternalLinkType.STATUSPAGE,
            defaults={"url": ""},
        )

        if not created and statuspage_link.url:
            sp_id = service.extract_incident_id_from_url(statuspage_link.url)
            if not sp_id:
                client.chat_postMessage(
                    channel=channel_id,
                    text="Could not determine the existing statuspage incident ID.",
                )
                return
            result = service.update_incident(
                incident_id=sp_id,
                status=status,
                message=message,
                components=components or None,
            )
            statuspage_url = service.get_incident_url(result["id"])
            client.chat_postMessage(
                channel=channel_id,
                text=f"Statuspage has been updated: {statuspage_url}",
            )
        else:
            if not title:
                title = incident.title
            try:
                result = service.create_incident(
                    title=title,
                    status=status,
                    message=message,
                    impact=impact,
                    components=components or None,
                )
            except Exception:
                if created:
                    statuspage_link.delete()
                raise
            statuspage_url = service.get_incident_url(result["id"])
            statuspage_link.url = statuspage_url
            statuspage_link.save(update_fields=["url"])
            client.chat_postMessage(
                channel=channel_id,
                text=f"Statuspage post created: {statuspage_url}",
            )
    except (requests.RequestException, KeyError):
        logger.exception("Failed to create/update statuspage incident")
        client.chat_postMessage(
            channel=channel_id,
            text="Something went wrong updating Statuspage. Please try again.",
        )
