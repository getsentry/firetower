from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.db import IntegrityError

from firetower.incidents.models import (
    ExternalLink,
    Incident,
    IncidentCounter,
    IncidentSeverity,
    IncidentStatus,
    TimelineEvent,
    TimelineEventSource,
    TimelineEventType,
)
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.incidents.timeline.events import (
    record_captain_changed,
    record_incident_created,
    record_severity_changed,
    record_status_changed,
    record_title_changed,
    record_visibility_changed,
)


@pytest.fixture
def users(db):
    first = User.objects.create_user(
        username="first@example.com",
        email="first@example.com",
        first_name="First",
        last_name="User",
    )
    second = User.objects.create_user(
        username="second@example.com",
        email="second@example.com",
        first_name="Second",
        last_name="User",
    )
    return first, second


@pytest.fixture
def incident(users):
    first, _ = users
    return Incident.objects.create(
        title="Original",
        severity=IncidentSeverity.P2,
        status=IncidentStatus.ACTIVE,
        captain=first,
        reporter=first,
    )


@pytest.mark.django_db
class TestTimelineEventHelpers:
    def test_every_internal_helper(self, incident, users):
        first, second = users
        occurred_at = datetime(2026, 8, 20, 15, tzinfo=UTC)

        record_incident_created(
            incident,
            severity="P2",
            actor=first,
            occurred_at=occurred_at,
        )
        record_status_changed(incident, "Active", "Mitigated", occurred_at=occurred_at)
        record_severity_changed(incident, "P2", "P1", occurred_at=occurred_at)
        record_captain_changed(incident, first, second, occurred_at=occurred_at)
        record_title_changed(incident, "Original", "Updated", occurred_at=occurred_at)
        record_visibility_changed(incident, False, True, occurred_at=occurred_at)

        events = list(incident.timeline_events.all())
        assert [event.source for event in events] == [TimelineEventSource.INTERNAL] * 6
        assert [event.event_type for event in events] == [
            TimelineEventType.INCIDENT_CREATED,
            TimelineEventType.STATUS_CHANGED,
            TimelineEventType.SEVERITY_CHANGED,
            TimelineEventType.CAPTAIN_CHANGED,
            TimelineEventType.TITLE_CHANGED,
            TimelineEventType.VISIBILITY_CHANGED,
        ]
        assert [event.payload for event in events] == [
            {"severity": "P2"},
            {"old": "Active", "new": "Mitigated"},
            {"old": "P2", "new": "P1"},
            {"old": "First User", "new": "Second User"},
            {"old": "Original", "new": "Updated"},
            {"old": False, "new": True},
        ]
        assert events[0].actor == first
        assert events[0].occurred_at == occurred_at
        assert all(event.occurred_at is not None for event in events)

    def test_captain_helper_records_unassigned(self, incident, users):
        first, _ = users
        event = record_captain_changed(incident, first, None)
        assert event.payload == {"old": "First User", "new": None}


@pytest.mark.django_db
class TestTimelinePersistence:
    def _create(self, users, *, context=None, **overrides):
        first, _ = users
        data = {
            "title": "Created",
            "severity": "P1",
            "captain": first.email,
            "reporter": first.email,
        }
        data.update(overrides)
        serializer = IncidentWriteSerializer(data=data, context=context or {})
        assert serializer.is_valid(), serializer.errors
        return serializer.save()

    def test_create_records_event_when_hooks_disabled(self, users, settings):
        settings.HOOKS_ENABLED = False
        incident = self._create(users)

        event = incident.timeline_events.get()
        assert event.event_type == TimelineEventType.INCIDENT_CREATED
        assert event.payload == {"severity": "P1"}
        assert event.occurred_at == incident.created_at
        assert event.actor is None

    @patch("firetower.incidents.serializers.on_incident_created")
    def test_create_skip_hooks_still_records_event(self, hook, users, settings):
        settings.HOOKS_ENABLED = True
        incident = self._create(users, context={"skip_hooks": True})
        assert incident.timeline_events.count() == 1
        hook.assert_not_called()

    def test_create_uses_acting_user_before_request_user(self, users):
        first, second = users
        request = type("Request", (), {"user": first})()
        incident = self._create(
            users,
            context={"acting_user": second, "request": request},
        )
        assert incident.timeline_events.get().actor == second

    def test_create_normalizes_anonymous_actor_and_uses_request(self, users):
        first, _ = users
        request = type("Request", (), {"user": first})()
        incident = self._create(
            users,
            context={"acting_user": AnonymousUser(), "request": request},
        )
        assert incident.timeline_events.get().actor == first

    def test_multi_field_update_records_shared_actor_and_time(self, incident, users):
        _, second = users
        serializer = IncidentWriteSerializer(
            incident,
            data={
                "status": "Mitigated",
                "severity": "P1",
                "captain": second.email,
                "title": "Updated",
                "is_private": True,
            },
            partial=True,
            context={"acting_user": second},
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()

        events = list(incident.timeline_events.all())
        assert [event.event_type for event in events] == [
            TimelineEventType.STATUS_CHANGED,
            TimelineEventType.SEVERITY_CHANGED,
            TimelineEventType.CAPTAIN_CHANGED,
            TimelineEventType.TITLE_CHANGED,
            TimelineEventType.VISIBILITY_CHANGED,
        ]
        assert len({event.occurred_at for event in events}) == 1
        assert {event.actor for event in events} == {second}
        assert events[2].payload == {
            "old": "First User",
            "new": "Second User",
        }

    @patch("firetower.incidents.serializers.on_incident_updated")
    def test_untracked_and_unchanged_updates_do_not_record_or_hook(
        self, hook, incident, settings
    ):
        settings.HOOKS_ENABLED = True
        serializer = IncidentWriteSerializer(
            incident,
            data={"description": "New description", "title": incident.title},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        assert incident.timeline_events.count() == 0
        hook.assert_not_called()

    @patch("firetower.incidents.serializers.on_incident_updated")
    def test_update_skip_hooks_still_records(self, hook, incident, settings):
        settings.HOOKS_ENABLED = True
        serializer = IncidentWriteSerializer(
            incident,
            data={"title": "Updated"},
            partial=True,
            context={"skip_hooks": True},
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        assert incident.timeline_events.count() == 1
        hook.assert_not_called()

    def test_update_rereads_locked_row_before_snapshot(self, incident):
        stale_instance = Incident.objects.get(pk=incident.pk)
        Incident.objects.filter(pk=incident.pk).update(status=IncidentStatus.MITIGATED)
        serializer = IncidentWriteSerializer(
            stale_instance,
            data={"status": "Done"},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()

        event = incident.timeline_events.get()
        assert event.payload == {"old": "Mitigated", "new": "Done"}

    @patch(
        "firetower.incidents.serializers.record_title_changed",
        side_effect=IntegrityError("timeline insert failed"),
    )
    def test_update_event_failure_rolls_back_local_writes(self, _, incident):
        serializer = IncidentWriteSerializer(
            incident,
            data={
                "title": "Updated",
                "external_links": {"datadog": "https://example.com/dashboard"},
            },
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors

        with pytest.raises(IntegrityError, match="timeline insert failed"):
            serializer.save()

        incident.refresh_from_db()
        assert incident.title == "Original"
        assert ExternalLink.objects.filter(incident=incident).count() == 0
        assert TimelineEvent.objects.count() == 0

    @patch(
        "firetower.incidents.serializers.record_incident_created",
        side_effect=IntegrityError("timeline insert failed"),
    )
    @patch(
        "firetower.incidents.serializers.adopt_on_create_enabled", return_value=False
    )
    def test_create_event_failure_rolls_back_incident_and_counter(self, _, __, users):
        IncidentCounter.objects.update_or_create(pk=1, defaults={"next_id": 2500})
        first, _ = users
        serializer = IncidentWriteSerializer(
            data={
                "title": "Created",
                "severity": "P1",
                "captain": first.email,
                "reporter": first.email,
            }
        )
        assert serializer.is_valid(), serializer.errors

        with pytest.raises(IntegrityError, match="timeline insert failed"):
            serializer.save()

        assert Incident.objects.count() == 0
        assert IncidentCounter.objects.get(pk=1).next_id == 2500

    def test_direct_orm_writes_do_not_record_events(self, incident):
        incident.title = "Direct update"
        incident.save()
        assert incident.timeline_events.count() == 0
