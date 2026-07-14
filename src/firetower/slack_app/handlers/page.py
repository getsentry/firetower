import logging
from typing import Any

from django.conf import settings

from firetower.incidents.hooks import (
    PAGING_POLICIES,
    get_pageable_policies,
    manual_page,
)
from firetower.incidents.models import IncidentStatus
from firetower.integrations.services.slack import escape_slack_text
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)

# Terminal statuses whose PagerDuty pages have already been resolved on
# mitigate/close. Paging one of these would re-trigger a fresh PD alert via the
# deterministic dedup key, so we block them.
CLOSED_STATUSES = {
    IncidentStatus.POSTMORTEM,
    IncidentStatus.DONE,
    IncidentStatus.CANCELED,
}


def _build_page_modal(
    incident_number: str,
    channel_id: str,
    policies: list[tuple[str, str]],
) -> dict:
    options = [
        {
            "text": {"type": "plain_text", "text": display_name},
            "value": policy_name,
        }
        for policy_name, display_name in policies
    ]
    return {
        "type": "modal",
        "callback_id": "page_incident_modal",
        "private_metadata": channel_id,
        "title": {"type": "plain_text", "text": incident_number},
        "submit": {"type": "plain_text", "text": "Page"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "Select which on-call escalation policies to page "
                        "for this incident."
                    ),
                },
            },
            {
                "type": "input",
                "block_id": "policies_block",
                "element": {
                    "type": "checkboxes",
                    "action_id": "policies",
                    "options": options,
                },
                "label": {"type": "plain_text", "text": "Who to page"},
            },
            {
                "type": "input",
                "block_id": "note_block",
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "note",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Optional context included in the page",
                    },
                },
                "label": {"type": "plain_text", "text": "Note"},
            },
        ],
    }


def handle_page_command(ack: Any, body: dict, command: dict, respond: Any) -> None:
    ack()
    channel_id = body.get("channel_id", "")
    incident = get_incident_from_channel(channel_id)
    if not incident:
        respond("Could not find an incident associated with this channel.")
        return

    if incident.status in CLOSED_STATUSES:
        respond(f"Cannot page {incident.incident_number} — it is {incident.status}.")
        return

    policies = get_pageable_policies()
    if not policies:
        respond("PagerDuty paging is not configured.")
        return

    trigger_id = body.get("trigger_id")
    if not trigger_id:
        respond("Could not open modal — missing trigger_id.")
        return

    from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415

    get_bolt_app().client.views_open(
        trigger_id=trigger_id,
        view=_build_page_modal(incident.incident_number, channel_id, policies),
    )


def handle_page_submission(ack: Any, body: dict, view: dict, client: Any) -> None:
    values = view.get("state", {}).get("values", {})
    selected = (
        values.get("policies_block", {}).get("policies", {}).get("selected_options")
        or []
    )
    policy_names = [opt["value"] for opt in selected]

    if not policy_names:
        ack(
            response_action="errors",
            errors={"policies_block": "Select at least one escalation policy to page."},
        )
        return

    ack()

    channel_id = view.get("private_metadata", "")
    incident = get_incident_from_channel(channel_id)
    if not incident:
        logger.error("Page submission: no incident for channel %s", channel_id)
        return

    # Status may have changed to terminal between opening and submitting the
    # modal; re-paging would re-trigger an already-resolved PD alert.
    if incident.status in CLOSED_STATUSES:
        logger.info(
            "Page submission: %s is %s, skipping page",
            incident.incident_number,
            incident.status,
        )
        client.chat_postMessage(
            channel=channel_id,
            text=f"Not paging {incident.incident_number} — it is now {incident.status}.",
        )
        return

    note = (
        values.get("note_block", {}).get("note", {}).get("value") or ""
    ).strip() or None

    paged = manual_page(incident, policy_names, channel_id=channel_id, note=note)

    pager_id = body.get("user", {}).get("id", "")
    incident_url = f"{settings.FIRETOWER_BASE_URL}/{incident.incident_number}"

    requested = set(policy_names)
    paged_text = ", ".join(
        f"*{PAGING_POLICIES[name].display_name}*"
        for name in PAGING_POLICIES
        if name in paged
    )
    failed_text = ", ".join(
        f"*{PAGING_POLICIES[name].display_name}*"
        for name in PAGING_POLICIES
        if name in requested and name not in paged
    )

    if paged_text and failed_text:
        message = (
            f"<@{pager_id}> paged {paged_text} for "
            f"<{incident_url}|{incident.incident_number}>. "
            f":warning: Failed to page {failed_text} — please escalate manually."
        )
    elif paged_text:
        message = (
            f"<@{pager_id}> paged {paged_text} for "
            f"<{incident_url}|{incident.incident_number}>."
        )
    elif failed_text:
        message = (
            f"<@{pager_id}> could not page {failed_text} for "
            f"<{incident_url}|{incident.incident_number}>. Please escalate manually."
        )
    else:
        logger.warning(
            "Page submission for %s produced no known policies (requested=%s)",
            incident.incident_number,
            policy_names,
        )
        return

    if note:
        message += f"\n*Note:* {escape_slack_text(note)}"

    client.chat_postMessage(channel=channel_id, text=message)
