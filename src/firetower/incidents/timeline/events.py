from datetime import datetime
from typing import TypedDict

from django.contrib.auth.models import User
from django.utils import timezone

from firetower.incidents.models import (
    Incident,
    TimelineEvent,
    TimelineEventSource,
    TimelineEventType,
)


class IncidentCreatedPayload(TypedDict):
    severity: str


class ChangedPayload(TypedDict):
    old: str
    new: str


class CaptainChangedPayload(TypedDict):
    old: str | None
    new: str | None


class VisibilityChangedPayload(TypedDict):
    old: bool
    new: bool


class NotePayload(TypedDict):
    text: str


class StatuspagePayload(TypedDict):
    message: str


class StatuspageUpdatePayload(TypedDict):
    message: str
    status: str


class PagerDutyPayload(TypedDict):
    service: str


def _record_event(
    incident: Incident,
    event_type: TimelineEventType,
    payload: object,
    *,
    actor: User | None,
    occurred_at: datetime | None,
    source: TimelineEventSource = TimelineEventSource.INTERNAL,
    link_url: str = "",
    external_id: str = "",
) -> TimelineEvent:
    return TimelineEvent.objects.create(
        incident=incident,
        source=source,
        event_type=event_type,
        occurred_at=occurred_at or timezone.now(),
        actor=actor,
        payload=payload,
        link_url=link_url,
        external_id=external_id,
    )


def record_incident_created(
    incident: Incident,
    *,
    severity: str,
    actor: User | None = None,
    occurred_at: datetime | None = None,
) -> TimelineEvent:
    payload: IncidentCreatedPayload = {"severity": severity}
    return _record_event(
        incident,
        TimelineEventType.INCIDENT_CREATED,
        payload,
        actor=actor,
        occurred_at=occurred_at,
    )


def record_status_changed(
    incident: Incident,
    old: str,
    new: str,
    *,
    actor: User | None = None,
    occurred_at: datetime | None = None,
) -> TimelineEvent:
    payload: ChangedPayload = {"old": old, "new": new}
    return _record_event(
        incident,
        TimelineEventType.STATUS_CHANGED,
        payload,
        actor=actor,
        occurred_at=occurred_at,
    )


def record_severity_changed(
    incident: Incident,
    old: str,
    new: str,
    *,
    actor: User | None = None,
    occurred_at: datetime | None = None,
) -> TimelineEvent:
    payload: ChangedPayload = {"old": old, "new": new}
    return _record_event(
        incident,
        TimelineEventType.SEVERITY_CHANGED,
        payload,
        actor=actor,
        occurred_at=occurred_at,
    )


def _display_name(user: User | None) -> str | None:
    if user is None:
        return None
    return user.get_full_name() or user.username


def record_captain_changed(
    incident: Incident,
    old: User | None,
    new: User | None,
    *,
    actor: User | None = None,
    occurred_at: datetime | None = None,
) -> TimelineEvent:
    payload: CaptainChangedPayload = {
        "old": _display_name(old),
        "new": _display_name(new),
    }
    return _record_event(
        incident,
        TimelineEventType.CAPTAIN_CHANGED,
        payload,
        actor=actor,
        occurred_at=occurred_at,
    )


def record_title_changed(
    incident: Incident,
    old: str,
    new: str,
    *,
    actor: User | None = None,
    occurred_at: datetime | None = None,
) -> TimelineEvent:
    payload: ChangedPayload = {"old": old, "new": new}
    return _record_event(
        incident,
        TimelineEventType.TITLE_CHANGED,
        payload,
        actor=actor,
        occurred_at=occurred_at,
    )


def record_visibility_changed(
    incident: Incident,
    old: bool,
    new: bool,
    *,
    actor: User | None = None,
    occurred_at: datetime | None = None,
) -> TimelineEvent:
    payload: VisibilityChangedPayload = {"old": old, "new": new}
    return _record_event(
        incident,
        TimelineEventType.VISIBILITY_CHANGED,
        payload,
        actor=actor,
        occurred_at=occurred_at,
    )


def record_statuspage_incident_created(
    incident: Incident,
    *,
    sp_incident_id: str,
    sp_url: str,
    message: str,
    occurred_at: datetime,
    actor: User | None = None,
) -> TimelineEvent:
    payload: StatuspagePayload = {"message": message}
    return _record_event(
        incident,
        TimelineEventType.STATUSPAGE_INCIDENT_CREATED,
        payload,
        actor=actor,
        occurred_at=occurred_at,
        source=TimelineEventSource.STATUSPAGE,
        link_url=sp_url,
        external_id=sp_incident_id,
    )


def record_statuspage_update_posted(
    incident: Incident,
    *,
    sp_update_id: str,
    sp_url: str,
    message: str,
    status: str,
    occurred_at: datetime,
    actor: User | None = None,
) -> TimelineEvent:
    payload: StatuspageUpdatePayload = {
        "message": message,
        "status": status,
    }
    return _record_event(
        incident,
        TimelineEventType.STATUSPAGE_UPDATE_POSTED,
        payload,
        actor=actor,
        occurred_at=occurred_at,
        source=TimelineEventSource.STATUSPAGE,
        link_url=sp_url,
        external_id=sp_update_id,
    )
