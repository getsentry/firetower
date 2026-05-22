import logging
from typing import Any

from slack_sdk.errors import SlackApiError

from firetower.auth.models import ExternalProfileType
from firetower.incidents.models import (
    ExternalLinkType,
    Incident,
    IncidentStatus,
)
from firetower.integrations.services.slack import escape_slack_text

logger = logging.getLogger(__name__)


def _format_incident_line(
    incident: Incident, slack_url: str | None, captain_slack_id: str | None
) -> str:
    if captain_slack_id:
        captain_display = f"<@{captain_slack_id}>"
    elif incident.captain:
        captain_name = (
            f"{incident.captain.first_name} {incident.captain.last_name}".strip()
            or "unassigned"
        )
        captain_display = escape_slack_text(captain_name)
    else:
        captain_display = "unassigned"

    title = escape_slack_text(incident.title)
    if slack_url:
        incident_label = f"<{slack_url}|{incident.incident_number}>"
    else:
        incident_label = incident.incident_number
    parts = [
        f"{incident.severity} {incident_label}: {title}",
        f"Captain: {captain_display}",
    ]
    return " | ".join(parts)


def _is_slack_guest(client: Any, user_id: str) -> bool:
    try:
        response = client.users_info(user=user_id)
        user = response.get("user", {})
        return bool(user.get("is_restricted") or user.get("is_ultra_restricted"))
    except SlackApiError:
        logger.exception("Failed to fetch Slack user info for %s", user_id)
        return False


def handle_list_command(
    ack: Any, body: dict, command: dict, respond: Any, client: Any = None
) -> None:
    ack()

    user_id = body.get("user_id", "")
    if client and user_id and _is_slack_guest(client, user_id):
        respond(
            "This command is not available to guest users.", response_type="ephemeral"
        )
        return

    incidents = (
        Incident.objects.filter(
            status__in=[IncidentStatus.ACTIVE, IncidentStatus.MITIGATED],
            is_private=False,
        )
        .select_related("captain")
        .prefetch_related("external_links", "captain__external_profiles")
        .order_by("-created_at")
    )

    slack_urls: dict[int, str] = {}
    for inc in incidents:
        for link in inc.external_links.all():
            if link.type == ExternalLinkType.SLACK:
                slack_urls[inc.id] = link.url
                break

    captain_slack_ids: dict[int, str] = {}
    for inc in incidents:
        if inc.captain_id and inc.captain_id not in captain_slack_ids:
            for profile in inc.captain.external_profiles.all():
                if profile.type == ExternalProfileType.SLACK:
                    captain_slack_ids[inc.captain_id] = profile.external_id
                    break

    active = [i for i in incidents if i.status == IncidentStatus.ACTIVE]
    mitigated = [i for i in incidents if i.status == IncidentStatus.MITIGATED]

    if not active and not mitigated:
        respond("No active or mitigated incidents.", response_type="ephemeral")
        return

    sections: list[str] = []
    if active:
        lines = [
            _format_incident_line(
                i, slack_urls.get(i.id), captain_slack_ids.get(i.captain_id)
            )
            for i in active
        ]
        sections.append("*Active Incidents*\n" + "\n".join(lines))
    if mitigated:
        lines = [
            _format_incident_line(
                i, slack_urls.get(i.id), captain_slack_ids.get(i.captain_id)
            )
            for i in mitigated
        ]
        sections.append("*Mitigated Incidents*\n" + "\n".join(lines))

    respond("\n\n".join(sections), response_type="ephemeral")
