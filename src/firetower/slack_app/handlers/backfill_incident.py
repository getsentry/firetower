import logging
import re
from typing import Any

from django.conf import settings

from firetower.auth.services import get_or_create_user_from_slack_id
from firetower.incidents.hooks import build_channel_name, build_channel_topic
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
)
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.incidents.services import sync_incident_participants_from_slack
from firetower.integrations.services import SlackService
from firetower.slack_app.handlers.utils import (
    _DEFAULT_SEVERITY,
    build_incident_form_blocks,
    parse_incident_form_values,
)

logger = logging.getLogger(__name__)
_slack_service = SlackService()


def _parse_channel_id_from_args(args: str) -> str | None:
    match = re.search(r"<#(C[A-Z0-9]+)\|", args)
    if match:
        return match.group(1)
    match = re.search(r"(C[A-Z0-9]+)", args)
    if match:
        return match.group(1)
    return None


def _build_backfill_modal(channel_id: str, user_id: str = "") -> dict:
    return {
        "type": "modal",
        "callback_id": "backfill_incident_modal",
        "title": {"type": "plain_text", "text": "Backfill Incident"},
        "submit": {"type": "plain_text", "text": "Backfill"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": build_incident_form_blocks(user_id=user_id),
        "private_metadata": channel_id,
    }


def _setup_channel_for_incident(
    incident: Any, channel_id: str, notify_user_id: str, client: Any
) -> None:
    joined = _slack_service.join_channel(channel_id)
    if not joined:
        base_url = settings.FIRETOWER_BASE_URL
        incident_url = f"{base_url}/{incident.incident_number}"
        try:
            client.chat_postMessage(
                channel=notify_user_id,
                text=(
                    f"Incident: {incident_url}\n"
                    f"The bot could not join <#{channel_id}>. "
                    f"Please invite the Firetower bot to the channel, "
                    f"then run `/ft backfill` again to retry setup."
                ),
            )
        except Exception:
            logger.exception(
                "Failed to notify user about join failure for backfill incident %s",
                incident.id,
            )
        return

    expected_name = build_channel_name(incident)
    channel_info = _slack_service.get_channel_info(channel_id)
    if channel_info and channel_info["name"] != expected_name:
        renamed = _slack_service.rename_channel(channel_id, expected_name)
        if not renamed:
            logger.warning(
                "Failed to rename channel %s to %s for incident %s",
                channel_id,
                expected_name,
                incident.id,
            )
            try:
                client.chat_postMessage(
                    channel=channel_id,
                    text=(
                        f"The bot could not rename this channel to `{expected_name}`. "
                        f"Please rename the channel manually."
                    ),
                )
            except Exception:
                logger.exception(
                    "Failed to post rename failure message for incident %s",
                    incident.id,
                )

    try:
        _slack_service.set_channel_topic(channel_id, build_channel_topic(incident))
    except Exception:
        logger.exception(
            "Failed to set channel topic for backfill incident %s", incident.id
        )

    base_url = settings.FIRETOWER_BASE_URL
    incident_url = f"{base_url}/{incident.incident_number}"
    try:
        _slack_service.add_bookmark(channel_id, "Firetower Incident", incident_url)
    except Exception:
        logger.exception("Failed to add bookmark for backfill incident %s", incident.id)

    try:
        sync_incident_participants_from_slack(incident, force=True)
    except Exception:
        logger.exception(
            "Failed to sync participants for backfill incident %s", incident.id
        )

    try:
        client.chat_postMessage(
            channel=notify_user_id,
            text=f"Channel setup complete for {incident.incident_number}: <#{channel_id}>",
        )
    except Exception:
        logger.exception(
            "Failed to send setup complete message for backfill incident %s",
            incident.id,
        )


def handle_backfill_command(ack: Any, body: dict, command: dict, respond: Any) -> None:
    ack()

    raw_text = (body.get("text") or "").strip()
    parts = raw_text.split(None, 1)
    args = parts[1] if len(parts) > 1 else ""

    channel_id = _parse_channel_id_from_args(args) if args else None
    if not channel_id:
        channel_id = body.get("channel_id", "")

    if not channel_id:
        respond(
            "Could not determine channel. Run this from an incident channel or specify one: `/ft backfill #channel`"
        )
        return

    channel_info = _slack_service.get_channel_info(channel_id)
    expected_prefix = f"{settings.PROJECT_KEY}-".lower()
    if not channel_info or not channel_info["name"].startswith(expected_prefix):
        respond(
            f"Backfill is only allowed on incident channels (name must start with `{expected_prefix}`)."
        )
        return

    existing_link = (
        ExternalLink.objects.filter(
            type=ExternalLinkType.SLACK,
            url__endswith=f"/archives/{channel_id}",
        )
        .select_related("incident")
        .first()
    )
    if existing_link:
        from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415

        slack_user_id = body.get("user_id", "")
        respond(
            f"This channel is already linked to {existing_link.incident.incident_number}. Retrying channel setup..."
        )
        _setup_channel_for_incident(
            existing_link.incident,
            channel_id,
            slack_user_id,
            get_bolt_app().client,
        )
        return

    trigger_id = body.get("trigger_id")
    if not trigger_id:
        respond("Could not open modal -- missing trigger_id.")
        return

    user_id = body.get("user_id", "")

    from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415

    get_bolt_app().client.views_open(
        trigger_id=trigger_id,
        view=_build_backfill_modal(channel_id=channel_id, user_id=user_id),
    )


def handle_backfill_submission(ack: Any, body: dict, view: dict, client: Any) -> None:
    form = parse_incident_form_values(view)

    if not form["title"]:
        ack(
            response_action="errors",
            errors={"title_block": "This field is required."},
        )
        return

    ack()

    channel_id = view.get("private_metadata", "")
    slack_user_id = body.get("user", {}).get("id", "")

    existing_link = (
        ExternalLink.objects.filter(
            type=ExternalLinkType.SLACK,
            url__endswith=f"/archives/{channel_id}",
        )
        .select_related("incident")
        .first()
    )
    if existing_link:
        client.chat_postMessage(
            channel=slack_user_id,
            text=f"This channel is already linked to {existing_link.incident.incident_number}.",
        )
        return

    user = get_or_create_user_from_slack_id(slack_user_id)
    if not user:
        client.chat_postMessage(
            channel=slack_user_id,
            text="Could not identify your Firetower account. Please try again.",
        )
        return

    captain_email = user.email
    if form["captain_slack_id"]:
        captain_user = get_or_create_user_from_slack_id(form["captain_slack_id"])
        if captain_user:
            captain_email = captain_user.email

    channel_url = _slack_service.build_channel_url(channel_id)
    channel_info = _slack_service.get_channel_info(channel_id)
    # Default to private when channel info is unavailable to avoid leaking
    # sensitive incident details if the Slack API call fails transiently.
    is_private = channel_info.get("is_private", True) if channel_info else True

    data: dict[str, Any] = {
        "title": form["title"],
        "severity": form["severity"] or _DEFAULT_SEVERITY.value,
        "description": form["description"],
        "impact_summary": form["impact_summary"],
        "captain": captain_email,
        "reporter": user.email,
        "is_private": is_private,
        "external_links": {"slack": channel_url},
    }
    if form["impact_type_tags"]:
        data["impact_type_tags"] = form["impact_type_tags"]
    if form["affected_service_tags"]:
        data["affected_service_tags"] = form["affected_service_tags"]
    if form["affected_region_tags"]:
        data["affected_region_tags"] = form["affected_region_tags"]

    serializer = IncidentWriteSerializer(data=data, context={"skip_hooks": True})
    if not serializer.is_valid():
        logger.error("Backfill incident validation failed: %s", serializer.errors)
        client.chat_postMessage(
            channel=slack_user_id,
            text="Something went wrong validating the incident. Please try again.",
        )
        return

    try:
        incident = serializer.save()
    except Exception:
        logger.exception("Failed to create backfill incident from Slack modal")
        client.chat_postMessage(
            channel=slack_user_id,
            text="Something went wrong creating the backfill incident. Please try again.",
        )
        return

    _setup_channel_for_incident(incident, channel_id, slack_user_id, client)
