import logging
from typing import Any

from firetower.auth.services import get_or_create_user_from_slack_id
from firetower.incidents.models import Incident, IncidentStatus
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.slack_app.handlers.utils import (
    build_incident_lifecycle_modal,
    get_incident_from_channel,
    parse_incident_form_values,
)

logger = logging.getLogger(__name__)


def _build_resolved_modal(incident: Incident, channel_id: str) -> dict:
    return build_incident_lifecycle_modal(
        incident=incident,
        channel_id=channel_id,
        title_text=incident.incident_number,
        callback_id="resolved_incident_modal",
        intro_text="This incident has been contained! Please confirm the details below.",
    )


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

    captain_slack_id = form["captain_slack_id"]
    severity = form["severity"]
    service_tier = form["service_tier"]

    errors: dict[str, str] = {}
    if not captain_slack_id:
        errors["captain_block"] = "An incident captain is required."
    if not severity:
        errors["severity_block"] = "Severity is required."
    if not form["title"]:
        errors["title_block"] = "This field is required."
    if not form["description"]:
        errors["description_block"] = "Description is required."
    if not form["impact_summary"]:
        errors["impact_summary_block"] = "Impact summary is required."
    if not form["impact_type_tags"]:
        errors["impact_type_block"] = "Select at least one impact type."
    if not service_tier:
        errors["service_tier_block"] = "Service tier is required."

    if errors:
        ack(response_action="errors", errors=errors)
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
        "service_tier": service_tier,
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
