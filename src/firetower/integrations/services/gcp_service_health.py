"""Read open Google Cloud incidents from the Personalized Service Health API."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import quote

import google.auth
from django.conf import settings
from google.auth.transport.requests import AuthorizedSession

from firetower.integrations.services.slack import escape_slack_text

logger = logging.getLogger(__name__)

API_BASE_URL = "https://servicehealth.googleapis.com/v1"
DASHBOARD_BASE_URL = "https://console.cloud.google.com/servicehealth/eventDetails"
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
REQUEST_TIMEOUT_SECONDS = 10
PAGE_SIZE = 100
MAX_PAGES = 5

RELEVANCE_RANK = {
    "IMPACTED": 4,
    "RELATED": 3,
    "PARTIALLY_RELATED": 2,
    "UNKNOWN": 1,
    "RELEVANCE_UNSPECIFIED": 1,
}
RELEVANCE_LABELS = {
    "IMPACTED": "impacting our project",
    "RELATED": "related to our project",
    "PARTIALLY_RELATED": "partially related",
}


@dataclass
class GcpIncident:
    event_id: str
    name: str
    title: str
    detailed_state: str
    relevance: str
    update_time: str
    start_time: datetime | None = None
    products: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)

    @property
    def dashboard_url(self) -> str:
        project = self.name.split("/")[1]
        return f"{DASHBOARD_BASE_URL}/{quote(self.name, safe='')}?project={project}"


def _parse_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(v for v in values if v))


def parse_event(event: dict[str, Any]) -> GcpIncident:
    name = event.get("name", "")
    impacts = event.get("eventImpacts") or []
    return GcpIncident(
        event_id=name.rsplit("/", 1)[-1],
        name=name,
        title=event.get("title") or "Untitled GCP incident",
        detailed_state=event.get("detailedState") or event.get("state", ""),
        relevance=event.get("relevance") or "UNKNOWN",
        update_time=event.get("updateTime", ""),
        start_time=_parse_time(event.get("startTime")),
        products=_unique(
            [(i.get("product") or {}).get("productName", "") for i in impacts]
        ),
        locations=_unique(
            [(i.get("location") or {}).get("locationName", "") for i in impacts]
        ),
    )


def select_relevant_incidents(events: list[dict[str, Any]]) -> list[GcpIncident]:
    """Dedupe events across projects and drop ones that don't affect us.

    The same incident is returned once per project; keep the copy with the
    highest relevance so the message reflects the most-affected project.
    """
    best: dict[str, GcpIncident] = {}
    for event in events:
        incident = parse_event(event)
        if incident.relevance == "NOT_IMPACTED":
            continue
        existing = best.get(incident.event_id)
        if existing is None or RELEVANCE_RANK.get(
            incident.relevance, 0
        ) > RELEVANCE_RANK.get(existing.relevance, 0):
            best[incident.event_id] = incident

    return sorted(
        best.values(),
        key=lambda i: (RELEVANCE_RANK.get(i.relevance, 0), i.update_time),
        reverse=True,
    )


def format_incidents_message(incidents: list[GcpIncident]) -> str:
    lines = [":cloud: *Open GCP incidents that may be relevant:*"]
    for incident in incidents:
        line = f"• <{incident.dashboard_url}|{escape_slack_text(incident.title)}>"

        details = []
        if incident.products:
            details.append(escape_slack_text(", ".join(incident.products)))
        if incident.locations:
            details.append("in " + escape_slack_text(", ".join(incident.locations)))
        if details:
            line += " — " + " ".join(details)

        meta = [incident.detailed_state]
        if label := RELEVANCE_LABELS.get(incident.relevance):
            meta.append(label)
        if incident.start_time:
            meta.append(f"started {incident.start_time:%Y-%m-%d %H:%M} UTC")
        line += f" ({', '.join(meta)})"
        lines.append(line)
    return "\n".join(lines)


class GcpServiceHealthService:
    @classmethod
    def from_settings(cls) -> "GcpServiceHealthService | None":
        config = getattr(settings, "GCP_SERVICE_HEALTH", None)
        if not config or not config.get("PROJECTS"):
            return None
        return cls(projects=config["PROJECTS"])

    def __init__(self, projects: list[str]) -> None:
        self.projects = projects

    def _list_project_events(
        self, session: AuthorizedSession, project: str
    ) -> list[dict[str, Any]]:
        url = f"{API_BASE_URL}/projects/{project}/locations/global/events"
        params: dict[str, Any] = {
            "filter": "category=INCIDENT state=ACTIVE",
            "pageSize": PAGE_SIZE,
        }
        events: list[dict[str, Any]] = []
        for _ in range(MAX_PAGES):
            response = session.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            body = response.json()
            events.extend(body.get("events", []))
            token = body.get("nextPageToken")
            if not token:
                break
            params["pageToken"] = token
        return events

    def list_active_incidents(self) -> list[GcpIncident]:
        """Return active GCP incidents that may affect any configured project."""
        credentials, _ = google.auth.default(scopes=SCOPES)
        session = AuthorizedSession(credentials)
        events: list[dict[str, Any]] = []
        for project in self.projects:
            try:
                events.extend(self._list_project_events(session, project))
            except Exception:
                logger.exception(
                    "Failed to list GCP Service Health events for %s", project
                )
        return select_relevant_incidents(events)
