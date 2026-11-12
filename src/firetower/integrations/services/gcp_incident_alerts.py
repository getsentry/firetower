"""
Parse Google Cloud Personalized Service Health alerts posted to Slack.

Cloud Monitoring posts these alerts through the "Google Cloud Notifications"
Slack app. Each message carries the Service Health event labels (event_id,
title, state, impacted products and locations) in its text, which is what we
extract here so new incidents can surface GCP incidents that may be related.
"""

import html
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from firetower.integrations.services.slack import escape_slack_text

CLOSED_STATES = {"CLOSED", "RESOLVED"}

_HEADER_RE = re.compile(r"^\*<(?P<url>[^|>]+)\|(?P<name>[^>]+)>\*")
_EVENT_ID_RE = re.compile(r"\bevent_id=(?P<value>[A-Za-z0-9_-]+)")
_STATE_RE = re.compile(r"\bstate=(?P<value>[A-Z_]+)")
_TITLE_RE = re.compile(r",title=(?P<value>[^}]*)\}")
_START_TIME_RE = re.compile(r"\bstartTime=(?P<value>[^,}]+)")
_PRODUCTS_RE = re.compile(r"\bimpactedProducts=\[(?P<value>[^\]]*)\]")
_LOCATIONS_RE = re.compile(r"\bimpactedLocations=\[(?P<value>[^\]]*)\]")
_DASHBOARD_RE = re.compile(
    r"<(?P<url>https://console\.cloud\.google\.com/servicehealth/[^|>]+)\|"
)


@dataclass
class GcpIncidentAlert:
    event_id: str
    title: str
    state: str
    message_ts: str
    alert_url: str
    dashboard_url: str | None = None
    start_time: datetime | None = None
    products: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)


def _search(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group("value").strip() if match else None


def _parse_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip().strip("'\"") for item in raw.split(",") if item.strip()]


def _parse_start_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def parse_gcp_incident_alert(
    message: dict[str, Any], policy_name: str
) -> GcpIncidentAlert | None:
    """Parse a Slack message into a GCP incident alert.

    Returns None when the message is not from the given alert policy or is
    missing the Service Health event id.
    """
    text = message.get("text") or ""
    header = _HEADER_RE.match(text)
    if not header or html.unescape(header.group("name")).strip() != policy_name:
        return None

    event_id = _search(_EVENT_ID_RE, text)
    if not event_id:
        return None

    dashboard = _DASHBOARD_RE.search(text)
    return GcpIncidentAlert(
        event_id=event_id,
        title=html.unescape(_search(_TITLE_RE, text) or "Unknown GCP incident"),
        state=_search(_STATE_RE, text) or "UNKNOWN",
        message_ts=message.get("ts", ""),
        alert_url=html.unescape(header.group("url")),
        dashboard_url=html.unescape(dashboard.group("url")) if dashboard else None,
        start_time=_parse_start_time(_search(_START_TIME_RE, text)),
        products=_parse_list(_search(_PRODUCTS_RE, text)),
        locations=_parse_list(_search(_LOCATIONS_RE, text)),
    )


def find_open_gcp_incidents(
    messages: list[dict[str, Any]], policy_name: str
) -> list[GcpIncidentAlert]:
    """Return the latest alert per GCP event, skipping events that have closed.

    The same event is posted once per monitored GCP project and again on each
    update, so alerts are deduplicated by event id and the newest one wins.
    """
    latest: dict[str, GcpIncidentAlert] = {}
    for message in messages:
        alert = parse_gcp_incident_alert(message, policy_name)
        if alert is None:
            continue
        existing = latest.get(alert.event_id)
        if existing is None or float(alert.message_ts or 0) > float(
            existing.message_ts or 0
        ):
            latest[alert.event_id] = alert

    open_alerts = [a for a in latest.values() if a.state not in CLOSED_STATES]
    return sorted(open_alerts, key=lambda a: float(a.message_ts or 0), reverse=True)


def format_gcp_incidents_message(
    alerts: list[GcpIncidentAlert],
    source_channel_id: str,
    permalink_for: Callable[[str], str],
) -> str:
    """Build the Slack message listing GCP incidents that may be relevant."""
    lines = [
        f":cloud: *Open GCP incidents that may be relevant* "
        f"(from <#{source_channel_id}>):"
    ]
    for alert in alerts:
        title = escape_slack_text(alert.title)
        link = alert.dashboard_url or alert.alert_url
        line = f"• <{link}|{title}>"

        details = []
        if alert.products:
            details.append(escape_slack_text(", ".join(alert.products)))
        if alert.locations:
            details.append("in " + escape_slack_text(", ".join(alert.locations)))
        if details:
            line += " — " + " ".join(details)

        meta = [alert.state]
        if alert.start_time:
            meta.append(f"started {alert.start_time:%Y-%m-%d %H:%M} UTC")
        line += f" ({', '.join(meta)})"

        if alert.message_ts:
            line += f" · <{permalink_for(alert.message_ts)}|alert>"
        lines.append(line)
    return "\n".join(lines)
