import logging
from typing import Any

from django.conf import settings

from firetower.auth.models import ExternalProfileType
from firetower.incidents.models import IncidentStatus
from firetower.integrations.services.slack import escape_slack_text
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)


def handle_status_command(ack: Any, body: dict, command: dict, respond: Any) -> None:
    ack()
    channel_id = body.get("channel_id", "")
    incident = get_incident_from_channel(channel_id)
    if not incident:
        respond("Could not find an incident associated with this channel.")
        return

    base_url = settings.FIRETOWER_BASE_URL
    inc_num = incident.incident_number
    if base_url:
        inc_display = f"<{base_url}/{inc_num}|{inc_num}>"
    else:
        inc_display = inc_num

    captain = incident.captain
    if captain:
        slack_profile = captain.external_profiles.filter(
            type=ExternalProfileType.SLACK
        ).first()
        if slack_profile:
            ic_display = f"<@{slack_profile.external_id}>"
        else:
            ic_name = captain.get_full_name() or captain.username
            ic_display = escape_slack_text(ic_name)
    else:
        ic_display = "unassigned"

    title = escape_slack_text(incident.title)
    created_ts = int(incident.created_at.timestamp())

    lines = [
        f"*{inc_display}* — {title}",
        f"Status: *{incident.status}* | Severity: *{incident.severity}* | IC: {ic_display}",
        f"Started: <!date^{created_ts}^{{date_short_pretty}} at {{time}}|{incident.created_at.isoformat()}>",
    ]

    if incident.status == IncidentStatus.MITIGATED and incident.time_mitigated:
        mitigated_ts = int(incident.time_mitigated.timestamp())
        lines.append(
            f"Mitigated: <!date^{mitigated_ts}^{{date_short_pretty}} at {{time}}|{incident.time_mitigated.isoformat()}>"
        )

    respond("\n".join(lines))
