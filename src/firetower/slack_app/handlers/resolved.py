import logging
from typing import Any

from firetower.auth.services import get_or_create_user_from_slack_id
from firetower.incidents.models import Incident, IncidentStatus
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.slack_app.handlers.utils import (
    build_incident_lifecycle_modal,
    build_incident_update_data,
    get_incident_from_channel,
    notify_submission_error,
    parse_incident_form_values,
    validate_lifecycle_form,
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
    # Parse without resolving tags so validation touches no DB before ack().
    form = parse_incident_form_values(view, resolve_tags=False)
    channel_id = view.get("private_metadata", "")

    errors = validate_lifecycle_form(form)
    if errors:
        ack(response_action="errors", errors=errors)
        return

    ack()

    user_id = body["user"]["id"]

    # Work runs after ack() so the modal closes immediately; any failure is
    # reported back to the submitter as an ephemeral message.
    try:
        incident = get_incident_from_channel(channel_id)
        captain_user = (
            get_or_create_user_from_slack_id(form["captain_slack_id"])
            if incident
            else None
        )
        if incident is None or captain_user is None:
            notify_submission_error(client, channel_id, user_id)
            return

        # Resolve/create inline tags only after validation passed.
        form = parse_incident_form_values(view)

        severity = form["severity"]
        if severity in ("P0", "P1", "P2"):
            target_status = IncidentStatus.POSTMORTEM
        else:
            target_status = IncidentStatus.DONE

        data = build_incident_update_data(form, target_status, captain_user.email)
        acting_user = get_or_create_user_from_slack_id(user_id)
        serializer = IncidentWriteSerializer(
            instance=incident,
            data=data,
            partial=True,
            context={"acting_user": acting_user},
        )
        if not serializer.is_valid():
            logger.error("Resolved update failed: %s", serializer.errors)
            notify_submission_error(client, channel_id, user_id)
            return
        serializer.save()
    except Exception:
        logger.exception("Failed to process resolved submission")
        notify_submission_error(client, channel_id, user_id)
        return

    client.chat_postMessage(
        channel=channel_id,
        text=(
            f"*{incident.incident_number} marked as {target_status}*\n"
            f"Severity: {severity} | Captain: {captain_user.get_full_name()}"
        ),
    )

    # TODO: Postmortem doc generation will be added in RELENG-466 (Notion integration)
