import logging
from typing import Any

from firetower.auth.models import ExternalProfileType
from firetower.auth.services import get_or_create_user_from_slack_id
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)


def _build_captain_modal(
    incident_number: str, channel_id: str, captain_slack_id: str | None
) -> dict:
    captain_element: dict = {
        "type": "users_select",
        "action_id": "captain_select",
        "placeholder": {"type": "plain_text", "text": "Select incident captain"},
    }
    if captain_slack_id:
        captain_element["initial_user"] = captain_slack_id

    return {
        "type": "modal",
        "callback_id": "captain_incident_modal",
        "private_metadata": channel_id,
        "title": {"type": "plain_text", "text": incident_number},
        "submit": {"type": "plain_text", "text": "Update"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "captain_block",
                "optional": True,
                "element": captain_element,
                "label": {"type": "plain_text", "text": "Incident Captain"},
            },
        ],
    }


def handle_captain_command(ack: Any, body: dict, command: dict, respond: Any) -> None:
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
        view=_build_captain_modal(
            incident.incident_number, channel_id, captain_slack_id
        ),
    )


def handle_captain_submission(ack: Any, body: dict, view: dict, client: Any) -> None:
    values = view.get("state", {}).get("values", {})
    channel_id = view.get("private_metadata", "")

    captain_slack_id = (
        values.get("captain_block", {}).get("captain_select", {}).get("selected_user")
    )

    ack()

    incident = get_incident_from_channel(channel_id)
    if not incident:
        logger.error("Captain submission: no incident for channel %s", channel_id)
        return

    if not captain_slack_id:
        client.chat_postMessage(
            channel=channel_id,
            text=f"*{incident.incident_number}* captain was not changed.",
        )
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

    serializer = IncidentWriteSerializer(
        instance=incident, data={"captain": captain_user.email}, partial=True
    )
    if not serializer.is_valid():
        logger.error("Captain update failed: %s", serializer.errors)
        client.chat_postMessage(
            channel=channel_id,
            text=f"Failed to update captain: {serializer.errors}",
        )
        return

    serializer.save()
