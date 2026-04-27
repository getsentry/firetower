import json
import logging
from typing import Any

import requests
from django.db import transaction

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
            key=lambda x: x.get("created_at", ""),
            reverse=True,
        )
        if incident_updates:
            latest_status = incident_updates[0].get("status", "investigating")
            for update in incident_updates:
                for component in update.get("affected_components") or []:
                    component_id = component.get("code", "")
                    if component_id and component_id not in affected_components:
                        affected_components[component_id] = component.get(
                            "new_status", "operational"
                        )
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
                    "text": f"*Title:* {statuspage_incident.get('name', '')}",
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
                    "placeholder": {
                        "type": "plain_text",
                        "text": incident_title,
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
            if statuspage_incident is None:
                logger.info(
                    "Removing stale Statuspage ExternalLink for incident %s "
                    "(Statuspage incident %s missing)",
                    incident.id,
                    sp_id,
                )
                statuspage_link.delete()

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


def _extract_submission_data(view: dict) -> dict[str, Any]:
    values = view.get("state", {}).get("values", {})
    channel_id = view.get("private_metadata", "")

    status = (
        values.get("status_block", {})
        .get("status_select", {})
        .get("selected_option", {})
        .get("value", "investigating")
    )
    title = values.get("title_block", {}).get("title_input", {}).get("value", "")
    message = values.get("message_block", {}).get("message_input", {}).get("value", "")
    impact = (
        values.get("impact_block", {})
        .get("impact_select", {})
        .get("selected_option", {})
        .get("value", "major")
    )

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

    return {
        "channel_id": channel_id,
        "status": status,
        "title": title,
        "message": message,
        "impact": impact,
        "components": components,
    }


def _build_component_warning_modal(
    data: dict[str, Any],
    non_operational: list[tuple[str, str]],
) -> dict[str, Any]:
    component_lines = "\n".join(
        f"• *{name}* — {status.replace('_', ' ')}" for name, status in non_operational
    )
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":warning: You're resolving this Statuspage incident, "
                    "but the following components are not set to *Operational*:\n\n"
                    f"{component_lines}"
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": "statuspage_reset_and_resolve",
                    "text": {
                        "type": "plain_text",
                        "text": "Set All Operational & Resolve",
                    },
                    "style": "primary",
                },
            ],
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": "statuspage_resolve_anyway",
                    "text": {
                        "type": "plain_text",
                        "text": "Resolve Anyway",
                    },
                    "style": "danger",
                },
            ],
        },
    ]
    return {
        "type": "modal",
        "private_metadata": json.dumps(data),
        "title": {"type": "plain_text", "text": "Confirm Resolution"},
        "close": {"type": "plain_text", "text": "Go Back"},
        "blocks": blocks,
    }


def _process_statuspage_submission(data: dict[str, Any], client: Any) -> bool:
    channel_id = data["channel_id"]
    status = data["status"]
    title = data["title"]
    message = data["message"]
    impact = data["impact"]
    components = data["components"]

    service = StatuspageService()
    if not service.configured:
        if channel_id:
            client.chat_postMessage(
                channel=channel_id,
                text="Statuspage is not configured. Please contact your administrator.",
            )
        return False

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
        return False

    try:
        with transaction.atomic():
            # Hold the row lock across the Statuspage API call so concurrent submits
            # serialize and only one external incident is created. Trade-off: a stuck
            # Statuspage API blocks DB writers on this row until REQUEST_TIMEOUT_SECONDS.
            statuspage_link, created = (
                ExternalLink.objects.select_for_update().get_or_create(
                    incident=incident,
                    type=ExternalLinkType.STATUSPAGE,
                    defaults={"url": ""},
                )
            )

            if not created and statuspage_link.url:
                sp_id = service.extract_incident_id_from_url(statuspage_link.url)
                if not sp_id:
                    client.chat_postMessage(
                        channel=channel_id,
                        text="Could not determine the existing statuspage incident ID.",
                    )
                    return False
                result = service.update_incident(
                    incident_id=sp_id,
                    status=status,
                    message=message,
                    components=components or None,
                )
                statuspage_url = service.get_incident_url(result["id"])
                success_message = f"Statuspage has been updated: {statuspage_url}"
            else:
                result = service.create_incident(
                    title=title,
                    status=status,
                    message=message,
                    impact=impact,
                    components=components or None,
                )
                statuspage_url = service.get_incident_url(result["id"])
                statuspage_link.url = statuspage_url
                statuspage_link.save(update_fields=["url"])
                success_message = f"Statuspage post created: {statuspage_url}"
        client.chat_postMessage(channel=channel_id, text=success_message)
    except Exception:
        logger.exception("Failed to create/update statuspage incident")
        client.chat_postMessage(
            channel=channel_id,
            text="Something went wrong updating Statuspage. Please try again.",
        )
        return False
    return True


def handle_statuspage_submission(ack: Any, body: dict, view: dict, client: Any) -> None:
    values = view.get("state", {}).get("values", {})
    errors: dict[str, str] = {}
    message = values.get("message_block", {}).get("message_input", {}).get("value", "")
    if not message:
        errors["message_block"] = "Message is required."
    if "title_block" in values:
        title = values["title_block"].get("title_input", {}).get("value", "")
        if not title:
            errors["title_block"] = "Title is required."
    if errors:
        ack(response_action="errors", errors=errors)
        return

    data = _extract_submission_data(view)

    if data["status"] == "resolved":
        non_operational = [
            (cid, status)
            for cid, status in data["components"].items()
            if status != "operational"
        ]
        if non_operational:
            service = StatuspageService()
            try:
                top_level, children_map = service.get_components()
            except requests.RequestException:
                top_level, children_map = [], {}
            all_components = {c["id"]: c["name"] for c in top_level}
            for children in children_map.values():
                for c in children:
                    all_components[c["id"]] = c["name"]
            labeled = [
                (all_components.get(cid, cid), status)
                for cid, status in non_operational
            ]
            ack(
                response_action="push",
                view=_build_component_warning_modal(data, labeled),
            )
            return

    ack()
    _process_statuspage_submission(data, client)


def handle_component_impact_select(ack: Any, body: dict) -> None:
    ack()


def handle_statuspage_reset_and_resolve(ack: Any, body: dict, client: Any) -> None:
    ack()
    view = body.get("view", {})
    data = json.loads(view.get("private_metadata", "{}"))
    data["components"] = dict.fromkeys(data.get("components", {}), "operational")
    success = _process_statuspage_submission(data, client)
    from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415

    if success:
        message = ":white_check_mark: All components set to operational and statuspage resolved."
    else:
        message = ":x: Something went wrong — check the incident channel for details."
    get_bolt_app().client.views_update(
        view_id=view["id"],
        view={
            "type": "modal",
            "clear_on_close": True,
            "title": {"type": "plain_text", "text": "Confirm Resolution"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message},
                },
            ],
        },
    )


def handle_statuspage_resolve_anyway(ack: Any, body: dict, client: Any) -> None:
    ack()
    view = body.get("view", {})
    data = json.loads(view.get("private_metadata", "{}"))
    success = _process_statuspage_submission(data, client)
    from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415

    if success:
        message = (
            ":white_check_mark: Statuspage resolved (component statuses left as-is)."
        )
    else:
        message = ":x: Something went wrong — check the incident channel for details."
    get_bolt_app().client.views_update(
        view_id=view["id"],
        view={
            "type": "modal",
            "clear_on_close": True,
            "title": {"type": "plain_text", "text": "Confirm Resolution"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message},
                },
            ],
        },
    )
