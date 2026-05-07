import logging
from typing import Any

from django.conf import settings

from firetower.auth.services import get_or_create_user_from_slack_id
from firetower.incidents.models import Tag, TagType
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.integrations.services import SlackService
from firetower.integrations.services.slack import escape_slack_text
from firetower.slack_app.handlers.utils import (
    build_incident_form_blocks,
    parse_incident_form_values,
)

logger = logging.getLogger(__name__)
_slack_service = SlackService()


def _build_new_incident_modal(channel_id: str = "", user_id: str = "") -> dict:
    blocks = build_incident_form_blocks(user_id=user_id)

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

    modal: dict[str, Any] = {
        "type": "modal",
        "callback_id": "new_incident_modal",
        "title": {"type": "plain_text", "text": "New Incident"},
        "submit": {"type": "plain_text", "text": "Create"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }
    if channel_id:
        modal["private_metadata"] = channel_id
    return modal


ACTION_ID_TO_TAG_TYPE = {
    "impact_type_tags": TagType.IMPACT_TYPE,
    "affected_service_tags": TagType.AFFECTED_SERVICE,
    "affected_region_tags": TagType.AFFECTED_REGION,
}


def handle_tag_options(ack: Any, payload: dict) -> None:
    action_id = payload.get("action_id", "")
    keyword = payload.get("value", "")

    tag_type = ACTION_ID_TO_TAG_TYPE.get(action_id)
    if not tag_type:
        ack(options=[])
        return

    qs = Tag.objects.filter(type=tag_type)
    if keyword:
        qs = qs.filter(name__icontains=keyword)

    options = [
        {"text": {"type": "plain_text", "text": tag.name}, "value": tag.name}
        for tag in qs.order_by("name")[:100]
    ]
    ack(options=options)


def handle_new_command(ack: Any, body: dict, command: dict, respond: Any) -> None:
    ack()
    trigger_id = body.get("trigger_id")
    if not trigger_id:
        respond("Could not open modal — missing trigger_id.")
        return

    channel_id = body.get("channel_id", "")
    user_id = body.get("user_id", "")

    from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415

    get_bolt_app().client.views_open(
        trigger_id=trigger_id,
        view=_build_new_incident_modal(channel_id=channel_id, user_id=user_id),
    )


def handle_new_incident_submission(
    ack: Any, body: dict, view: dict, client: Any
) -> None:
    form = parse_incident_form_values(view)

    values = view.get("state", {}).get("values", {})
    private_selections = (
        values.get("private_block", {}).get("is_private", {}).get("selected_options")
        or []
    )
    is_private = any(opt.get("value") == "private" for opt in private_selections)

    if not form["title"]:
        ack(
            response_action="errors",
            errors={"title_block": "This field is required."},
        )
        return

    ack()

    slack_user_id = body.get("user", {}).get("id", "")
    user = get_or_create_user_from_slack_id(slack_user_id)
    if not user:
        client.chat_postMessage(
            channel=slack_user_id,
            text="Could not identify your Firetower account. Please try again or create the incident manually.",
        )
        return

    captain_email = user.email
    if form["captain_slack_id"]:
        captain_user = get_or_create_user_from_slack_id(form["captain_slack_id"])
        if captain_user:
            captain_email = captain_user.email

    data: dict[str, Any] = {
        "title": form["title"],
        "severity": form["severity"],
        "description": form["description"],
        "impact_summary": form["impact_summary"],
        "captain": captain_email,
        "reporter": user.email,
        "is_private": is_private,
    }
    if form["impact_type_tags"]:
        data["impact_type_tags"] = form["impact_type_tags"]
    if form["affected_service_tags"]:
        data["affected_service_tags"] = form["affected_service_tags"]
    if form["affected_region_tags"]:
        data["affected_region_tags"] = form["affected_region_tags"]

    serializer = IncidentWriteSerializer(data=data)
    if not serializer.is_valid():
        logger.error("Incident validation failed: %s", serializer.errors)
        client.chat_postMessage(
            channel=slack_user_id,
            text="Something went wrong validating your incident. Please try again.",
        )
        return

    try:
        incident = serializer.save()
    except Exception:
        logger.exception("Failed to create incident from Slack modal")
        client.chat_postMessage(
            channel=slack_user_id,
            text=(
                "Something went wrong creating your incident. "
                "Please create a Slack channel manually for incident coordination "
                "and let #team-sre know."
            ),
        )
        return

    try:
        base_url = settings.FIRETOWER_BASE_URL
        incident_url = f"{base_url}/{incident.incident_number}"
        slack_link = incident.external_links_dict.get("slack", "")

        channel_id = (
            _slack_service.parse_channel_id_from_url(slack_link) if slack_link else None
        )

        dm_message = "The incident has been created, details below.\n\n"
        dm_message += f"Incident: {incident_url}\n"
        if channel_id:
            dm_message += f"Slack channel: <#{channel_id}>"

        client.chat_postMessage(channel=slack_user_id, text=dm_message)

        invoking_channel = view.get("private_metadata", "")
        feed_channel_id = settings.SLACK.get("INCIDENT_FEED_CHANNEL_ID", "")
        if (
            invoking_channel
            and not is_private
            and invoking_channel != slack_user_id
            and invoking_channel != feed_channel_id
        ):
            channel_message = (
                f"A {incident.severity} incident has been created.\n"
                f"<{incident_url}|{incident.incident_number} {escape_slack_text(incident.title)}>"
            )
            if channel_id:
                channel_message += (
                    f"\n\nFor those involved, please join <#{channel_id}>"
                )
            _slack_service.join_channel(invoking_channel)
            client.chat_postMessage(channel=invoking_channel, text=channel_message)
    except Exception:
        logger.exception("Failed to send incident creation notifications")
