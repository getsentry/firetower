import logging
from typing import Any

from slack_sdk.errors import SlackApiError

from firetower.incidents.models import (
    ExternalLinkType,
    Incident,
    IncidentStatus,
)
from firetower.integrations.services.slack import escape_slack_text

logger = logging.getLogger(__name__)


def _format_incident_line(incident: Incident, slack_url: str | None) -> str:
    captain_name = (
        f"{incident.captain.first_name} {incident.captain.last_name}".strip()
        or "unassigned"
        if incident.captain
        else "unassigned"
    )
    title = escape_slack_text(incident.title)
    parts = [
        f"{incident.severity} {incident.incident_number}: {title}",
        f"Captain: {escape_slack_text(captain_name)}",
    ]
    if slack_url:
        parts.append(f"<{slack_url}|Slack>")
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
        respond("This command is not available to guest users.")
        return

    incidents = (
        Incident.objects.filter(
            status__in=[IncidentStatus.ACTIVE, IncidentStatus.MITIGATED],
            is_private=False,
        )
        .select_related("captain")
        .prefetch_related("external_links")
        .order_by("-created_at")
    )

    slack_urls: dict[int, str] = {}
    for inc in incidents:
        for link in inc.external_links.all():
            if link.type == ExternalLinkType.SLACK:
                slack_urls[inc.id] = link.url
                break

    active = [i for i in incidents if i.status == IncidentStatus.ACTIVE]
    mitigated = [i for i in incidents if i.status == IncidentStatus.MITIGATED]

    if not active and not mitigated:
        respond("No active or mitigated incidents.")
        return

    sections: list[str] = []
    if active:
        lines = [_format_incident_line(i, slack_urls.get(i.id)) for i in active]
        sections.append("*Active Incidents*\n" + "\n".join(lines))
    if mitigated:
        lines = [_format_incident_line(i, slack_urls.get(i.id)) for i in mitigated]
        sections.append("*Mitigated Incidents*\n" + "\n".join(lines))

    respond("\n\n".join(sections))
