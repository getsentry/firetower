from typing import Any

from firetower.incidents.models import (
    ExternalLinkType,
    Incident,
    IncidentStatus,
)


def _format_incident_line(incident: Incident, slack_url: str | None) -> str:
    captain_name = (
        f"{incident.captain.first_name} {incident.captain.last_name}".strip()
        or "unassigned"
        if incident.captain
        else "unassigned"
    )
    parts = [
        f"{incident.severity} {incident.incident_number}: {incident.title}",
        f"Captain: {captain_name}",
    ]
    if slack_url:
        parts.append(f"<{slack_url}|Slack>")
    return " | ".join(parts)


def handle_list_command(ack: Any, body: dict, command: dict, respond: Any) -> None:
    ack()

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
