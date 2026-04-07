import logging
from typing import Any

from firetower.auth.models import ExternalProfileType
from firetower.auth.services import get_or_create_user_from_slack_id
from firetower.incidents.models import IncidentSeverity, IncidentStatus
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)


def _build_resolved_modal(
    incident_number: str,
    channel_id: str,
    current_severity: str,
    captain_slack_id: str | None,
) -> dict:
    severity_options = [
        {
            "text": {"type": "plain_text", "text": sev.label},
            "value": sev.value,
        }
        for sev in IncidentSeverity
    ]
    initial_severity = next(
        (opt for opt in severity_options if opt["value"] == current_severity),
        severity_options[2],
    )

    captain_element: dict = {
        "type": "users_select",
        "action_id": "captain_select",
        "placeholder": {"type": "plain_text", "text": "Select incident captain"},
    }
    if captain_slack_id:
        captain_element["initial_user"] = captain_slack_id

    return {
        "type": "modal",
        "callback_id": "resolved_incident_modal",
        "private_metadata": channel_id,
        "title": {"type": "plain_text", "text": incident_number},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "This incident has been contained! Please confirm the final severity and incident captain.",
                },
            },
            {
                "type": "input",
                "block_id": "severity_block",
                "element": {
                    "type": "static_select",
                    "action_id": "severity_select",
                    "options": severity_options,
                    "initial_option": initial_severity,
                },
                "label": {"type": "plain_text", "text": "Severity"},
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

    captain_slack_id = None
    if incident.captain:
        slack_profile = incident.captain.external_profiles.filter(
            type=ExternalProfileType.SLACK
        ).first()
        if slack_profile:
            captain_slack_id = slack_profile.external_id

    from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415

    get_bolt_app().client.views_open(
        trigger_id=trigger_id,
        view=_build_resolved_modal(
            incident.incident_number,
            channel_id,
            incident.severity,
            captain_slack_id,
        ),
    )


def handle_resolved_submission(ack: Any, body: dict, view: dict, client: Any) -> None:
    values = view.get("state", {}).get("values", {})
    channel_id = view.get("private_metadata", "")

    severity = (
        values.get("severity_block", {})
        .get("severity_select", {})
        .get("selected_option", {})
        .get("value", "")
    )
    captain_slack_id = (
        values.get("captain_block", {}).get("captain_select", {}).get("selected_user")
    )

    if not captain_slack_id:
        ack(
            response_action="errors",
            errors={"captain_block": "An incident captain is required."},
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
