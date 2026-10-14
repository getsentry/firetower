from typing import assert_never, cast

from firetower.incidents.models import TimelineEvent, TimelineEventType
from firetower.incidents.timeline.events import (
    CaptainChangedPayload,
    ChangedPayload,
    IncidentCreatedPayload,
    NotePayload,
    PagerDutyPayload,
    StatuspagePayload,
    StatuspageUpdatePayload,
    VisibilityChangedPayload,
)


def _display_statuspage_status(status: str) -> str:
    return status.replace("_", " ").title()


def render_timeline_event(event: TimelineEvent) -> str:
    try:
        event_type = TimelineEventType(event.event_type)

        match event_type:
            case TimelineEventType.NOTE:
                note = cast(NotePayload, event.payload)
                return note["text"]
            case TimelineEventType.INCIDENT_CREATED:
                created = cast(IncidentCreatedPayload, event.payload)
                return f"Incident created at severity {created['severity']}"
            case TimelineEventType.STATUS_CHANGED:
                status = cast(ChangedPayload, event.payload)
                return f"Status changed: {status['old']} → {status['new']}"
            case TimelineEventType.SEVERITY_CHANGED:
                severity = cast(ChangedPayload, event.payload)
                return f"Severity changed: {severity['old']} → {severity['new']}"
            case TimelineEventType.CAPTAIN_CHANGED:
                captain = cast(CaptainChangedPayload, event.payload)
                old_captain = captain["old"] or "Unassigned"
                new_captain = captain["new"] or "Unassigned"
                return f"Captain changed: {old_captain} → {new_captain}"
            case TimelineEventType.TITLE_CHANGED:
                title = cast(ChangedPayload, event.payload)
                return f"Title changed: {title['old']} → {title['new']}"
            case TimelineEventType.VISIBILITY_CHANGED:
                visibility = cast(VisibilityChangedPayload, event.payload)
                old_visibility = "Private" if visibility["old"] else "Public"
                new_visibility = "Private" if visibility["new"] else "Public"
                return f"Visibility changed: {old_visibility} → {new_visibility}"
            case TimelineEventType.STATUSPAGE_INCIDENT_CREATED:
                statuspage_incident = cast(StatuspagePayload, event.payload)
                return f'Statuspage incident posted: "{statuspage_incident["message"]}"'
            case TimelineEventType.STATUSPAGE_UPDATE_POSTED:
                statuspage_update = cast(StatuspageUpdatePayload, event.payload)
                old_status = statuspage_update.get("old_status")
                new_status = statuspage_update.get("new_status")
                message = statuspage_update["message"]
                if old_status and new_status:
                    displayed_new_status = _display_statuspage_status(new_status)
                    if old_status == new_status:
                        return (
                            f'Statuspage update ({displayed_new_status}): "{message}"'
                        )
                    displayed_old_status = _display_statuspage_status(old_status)
                    return (
                        f"Statuspage update: {displayed_old_status} → "
                        f'{displayed_new_status} — "{message}"'
                    )
                return f'Statuspage update: "{message}"'
            case TimelineEventType.PAGERDUTY_INCIDENT_TRIGGERED:
                pagerduty = cast(PagerDutyPayload, event.payload)
                return f"PagerDuty page triggered for {pagerduty['service']}"
            case _:
                assert_never(event_type)
    except (KeyError, TypeError, ValueError):
        return "Timeline event could not be rendered."
