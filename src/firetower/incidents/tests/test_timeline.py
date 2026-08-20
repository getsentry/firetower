from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.db import IntegrityError
from rest_framework.test import APIClient

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
from firetower.incidents.services import ParticipantsSyncStats
from firetower.incidents.timeline.events import (
    record_captain_changed,
    record_incident_created,
    record_severity_changed,
    record_status_changed,
    record_title_changed,
    record_visibility_changed,
)
from firetower.incidents.timeline.render import render_timeline_event


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


class TestTimelineRenderer:
    @pytest.mark.parametrize(
        ("event_type", "payload", "expected"),
        [
            (TimelineEventType.NOTE, {"text": "A note"}, "A note"),
            (
                TimelineEventType.INCIDENT_CREATED,
                {"severity": "P1"},
                "Incident created at severity P1",
            ),
            (
                TimelineEventType.STATUS_CHANGED,
                {"old": "Active", "new": "Mitigated"},
                "Status changed: Active → Mitigated",
            ),
            (
                TimelineEventType.SEVERITY_CHANGED,
                {"old": "P2", "new": "P1"},
                "Severity changed: P2 → P1",
            ),
            (
                TimelineEventType.CAPTAIN_CHANGED,
                {"old": None, "new": "First User"},
                "Captain changed: Unassigned → First User",
            ),
            (
                TimelineEventType.TITLE_CHANGED,
                {"old": "Old", "new": "New"},
                "Title changed: Old → New",
            ),
            (
                TimelineEventType.VISIBILITY_CHANGED,
                {"old": False, "new": True},
                "Visibility changed: Public → Private",
            ),
            (
                TimelineEventType.STATUSPAGE_INCIDENT_CREATED,
                {"message": "Investigating"},
                'Statuspage incident posted: "Investigating"',
            ),
            (
                TimelineEventType.STATUSPAGE_UPDATE_POSTED,
                {"message": "Monitoring"},
                'Statuspage update: "Monitoring"',
            ),
            (
                TimelineEventType.PAGERDUTY_INCIDENT_TRIGGERED,
                {"service": "Backend"},
                "PagerDuty page triggered for Backend",
            ),
        ],
    )
    def test_renders_every_declared_event_type(self, event_type, payload, expected):
        event = TimelineEvent(event_type=event_type, payload=payload)
        assert render_timeline_event(event) == expected


@pytest.mark.django_db
class TestTimelineEventAPI:
    def setup_method(self):
        self.client = APIClient()
        self.reader = User.objects.create_user(
            username="reader@example.com", email="reader@example.com"
        )
        self.captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Timeline",
            last_name="Captain",
        )
        self.captain.userprofile.avatar_url = "https://example.com/avatar.png"
        self.captain.userprofile.save()

    def _incident(self, **overrides):
        values = {
            "title": "Timeline incident",
            "severity": IncidentSeverity.P1,
            "captain": self.captain,
        }
        values.update(overrides)
        return Incident.objects.create(**values)

    def _url(self, incident):
        return f"/api/ui/incidents/{incident.incident_number}/timeline-events/"

    def test_authenticated_api_request_is_creation_actor(self):
        self.client.force_authenticate(self.reader)
        response = self.client.post(
            "/api/incidents/",
            {
                "title": "Created through API",
                "severity": "P1",
                "captain": self.captain.email,
                "reporter": self.reader.email,
            },
            format="json",
        )

        assert response.status_code == 201
        incident = Incident.objects.get(title="Created through API")
        assert incident.timeline_events.get().actor == self.reader

    def test_returns_chronological_nonpaginated_events_and_nullable_actors(self):
        incident = self._incident()
        later = datetime(2026, 8, 20, 16, tzinfo=UTC)
        earlier = datetime(2026, 8, 20, 15, tzinfo=UTC)
        record_status_changed(
            incident,
            "Active",
            "Mitigated",
            actor=self.captain,
            occurred_at=later,
        )
        record_incident_created(
            incident,
            severity="P1",
            occurred_at=earlier,
        )

        self.client.force_authenticate(self.reader)
        response = self.client.get(self._url(incident))

        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert [item["event_type"] for item in response.data] == [
            "incident_created",
            "status_changed",
        ]
        assert response.data[0]["actor"] is None
        assert response.data[1]["actor"] == {
            "email": "captain@example.com",
            "name": "Timeline Captain",
            "avatar_url": "https://example.com/avatar.png",
        }
        assert response.data[1]["summary"] == "Status changed: Active → Mitigated"
        assert response.data[1]["payload"] == {
            "old": "Active",
            "new": "Mitigated",
        }
        assert response.data[1]["link_url"] == ""
        assert response.data[1]["external_id"] == ""

    def test_empty_and_read_only(self):
        incident = self._incident()
        self.client.force_authenticate(self.reader)
        assert self.client.get(self._url(incident)).data == []
        assert self.client.post(self._url(incident), {}).status_code == 405

    def test_nonexistent_incident_returns_404(self, settings):
        self.client.force_authenticate(self.reader)
        response = self.client.get(
            f"/api/ui/incidents/{settings.PROJECT_KEY}-99999/timeline-events/"
        )
        assert response.status_code == 404

    @pytest.mark.parametrize("role", ["captain", "reporter", "participant"])
    def test_authorized_private_roles_can_read(self, role):
        kwargs = {"is_private": True}
        if role == "captain":
            kwargs["captain"] = self.reader
        elif role == "reporter":
            kwargs["reporter"] = self.reader
        incident = self._incident(**kwargs)
        if role == "participant":
            incident.participants.add(self.reader)
        record_incident_created(incident, severity="P1")

        self.client.force_authenticate(self.reader)
        response = self.client.get(self._url(incident))
        assert response.status_code == 200
        assert len(response.data) == 1

    @patch(
        "firetower.incidents.views.sync_incident_participants_from_slack",
        return_value=ParticipantsSyncStats(),
    )
    def test_unauthorized_private_incident_returns_404_without_data(self, _):
        incident = self._incident(is_private=True)
        record_incident_created(incident, severity="P1")
        self.client.force_authenticate(self.reader)
        response = self.client.get(self._url(incident))
        assert response.status_code == 404

    @patch("firetower.incidents.views.sync_incident_participants_from_slack")
    def test_private_slack_member_fallback_sync(self, sync):
        incident = self._incident(is_private=True)
        record_incident_created(incident, severity="P1")

        def add_reader(inc, force=False):
            assert force is True
            inc.participants.add(self.reader)
            return ParticipantsSyncStats(added=1)

        sync.side_effect = add_reader
        self.client.force_authenticate(self.reader)
        response = self.client.get(self._url(incident))
        assert response.status_code == 200
        assert len(response.data) == 1

    @patch(
        "firetower.incidents.views.sync_incident_participants_from_slack",
        return_value=ParticipantsSyncStats(),
    )
    def test_current_visibility_exposes_complete_history_after_becoming_public(self, _):
        incident = self._incident(is_private=True)
        record_title_changed(incident, "Secret title", "Private-period title")

        self.client.force_authenticate(self.reader)
        assert self.client.get(self._url(incident)).status_code == 404

        Incident.objects.filter(pk=incident.pk).update(is_private=False)
        response = self.client.get(self._url(incident))
        assert response.status_code == 200
        assert [item["summary"] for item in response.data] == [
            "Title changed: Secret title → Private-period title"
        ]
