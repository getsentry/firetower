from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from firetower.integrations.services.gcp_service_health import (
    GcpServiceHealthService,
    format_incidents_message,
    parse_event,
    select_relevant_incidents,
)


def _event(
    project: str = "internal-sentry",
    event_id: str = "LDYWVWM",
    relevance: str = "RELATED",
    update_time: str = "2026-11-12T08:00:00Z",
    title: str = "VM to VM communication",
) -> dict:
    return {
        "name": f"projects/{project}/locations/global/events/{event_id}",
        "title": title,
        "category": "INCIDENT",
        "state": "ACTIVE",
        "detailedState": "CONFIRMED",
        "relevance": relevance,
        "updateTime": update_time,
        "startTime": "2026-11-12T07:48:02Z",
        "eventImpacts": [
            {
                "product": {"productName": "Virtual Private Cloud (VPC)"},
                "location": {"locationName": "us-east1"},
            },
            {
                "product": {"productName": "Virtual Private Cloud (VPC)"},
                "location": {"locationName": "us-south1"},
            },
        ],
    }


class TestParseEvent:
    def test_parses_event_fields(self):
        incident = parse_event(_event())

        assert incident.event_id == "LDYWVWM"
        assert incident.title == "VM to VM communication"
        assert incident.detailed_state == "CONFIRMED"
        assert incident.relevance == "RELATED"
        assert incident.start_time == datetime(2026, 11, 12, 7, 48, 2, tzinfo=UTC)
        assert incident.products == ["Virtual Private Cloud (VPC)"]
        assert incident.locations == ["us-east1", "us-south1"]
        assert incident.dashboard_url == (
            "https://console.cloud.google.com/servicehealth/eventDetails/"
            "projects%2Finternal-sentry%2Flocations%2Fglobal%2Fevents%2FLDYWVWM"
            "?project=internal-sentry"
        )

    def test_handles_missing_optional_fields(self):
        incident = parse_event(
            {"name": "projects/p/locations/global/events/E1", "state": "ACTIVE"}
        )

        assert incident.title == "Untitled GCP incident"
        assert incident.detailed_state == "ACTIVE"
        assert incident.relevance == "UNKNOWN"
        assert incident.start_time is None
        assert incident.products == []
        assert incident.locations == []


class TestSelectRelevantIncidents:
    def test_dedupes_across_projects_keeping_highest_relevance(self):
        incidents = select_relevant_incidents(
            [
                _event(project="sentry-s4s2", relevance="PARTIALLY_RELATED"),
                _event(project="internal-sentry", relevance="IMPACTED"),
            ]
        )

        assert len(incidents) == 1
        assert incidents[0].relevance == "IMPACTED"
        assert incidents[0].name.startswith("projects/internal-sentry/")

    def test_drops_not_impacted_events(self):
        incidents = select_relevant_incidents(
            [
                _event(event_id="A", relevance="NOT_IMPACTED"),
                _event(event_id="B", relevance="UNKNOWN"),
            ]
        )

        assert [i.event_id for i in incidents] == ["B"]

    def test_sorts_by_relevance_then_recency(self):
        incidents = select_relevant_incidents(
            [
                _event(event_id="OLD", relevance="RELATED", update_time="1"),
                _event(event_id="NEW", relevance="RELATED", update_time="2"),
                _event(event_id="TOP", relevance="IMPACTED", update_time="0"),
            ]
        )

        assert [i.event_id for i in incidents] == ["TOP", "NEW", "OLD"]


class TestFormatIncidentsMessage:
    def test_formats_incident_lines(self):
        incident = parse_event(_event(title="A <b> & c"))

        message = format_incidents_message([incident])

        assert message.startswith(":cloud: *Open GCP incidents that may be relevant:*")
        assert f"• <{incident.dashboard_url}|A &lt;b&gt; &amp; c>" in message
        assert "Virtual Private Cloud (VPC) in us-east1, us-south1" in message
        assert (
            "(CONFIRMED, related to our project, started 2026-11-12 07:48 UTC)"
            in message
        )

    def test_omits_label_for_unknown_relevance(self):
        message = format_incidents_message([parse_event(_event(relevance="UNKNOWN"))])

        assert "(CONFIRMED, started" in message


class TestGcpServiceHealthService:
    def test_from_settings_returns_none_when_unconfigured(self, settings):
        settings.GCP_SERVICE_HEALTH = None
        assert GcpServiceHealthService.from_settings() is None

        settings.GCP_SERVICE_HEALTH = {"PROJECTS": []}
        assert GcpServiceHealthService.from_settings() is None

    def test_from_settings(self, settings):
        settings.GCP_SERVICE_HEALTH = {"PROJECTS": ["internal-sentry"]}
        service = GcpServiceHealthService.from_settings()
        assert service is not None
        assert service.projects == ["internal-sentry"]

    def _response(self, body: dict) -> MagicMock:
        response = MagicMock()
        response.json.return_value = body
        return response

    @patch("firetower.integrations.services.gcp_service_health.AuthorizedSession")
    @patch(
        "firetower.integrations.services.gcp_service_health.google.auth.default",
        return_value=(MagicMock(), "snty-tools"),
    )
    def test_lists_active_incidents_across_projects(self, _, mock_session_cls):
        session = mock_session_cls.return_value
        session.get.side_effect = [
            self._response({"events": [_event(event_id="A")], "nextPageToken": "tok"}),
            self._response({"events": [_event(event_id="B")]}),
            self._response({"events": [_event(project="sentry-s4s2", event_id="A")]}),
        ]

        service = GcpServiceHealthService(["internal-sentry", "sentry-s4s2"])
        incidents = service.list_active_incidents()

        assert sorted(i.event_id for i in incidents) == ["A", "B"]
        first_call = session.get.call_args_list[0]
        assert first_call.args[0] == (
            "https://servicehealth.googleapis.com/v1/projects/internal-sentry/"
            "locations/global/events"
        )
        assert first_call.kwargs["params"]["filter"] == "category=INCIDENT state=ACTIVE"
        assert session.get.call_args_list[1].kwargs["params"]["pageToken"] == "tok"
        assert "sentry-s4s2" in session.get.call_args_list[2].args[0]

    @patch("firetower.integrations.services.gcp_service_health.AuthorizedSession")
    @patch(
        "firetower.integrations.services.gcp_service_health.google.auth.default",
        return_value=(MagicMock(), "snty-tools"),
    )
    def test_skips_projects_that_fail(self, _, mock_session_cls):
        session = mock_session_cls.return_value
        failing = MagicMock()
        failing.raise_for_status.side_effect = Exception("403")
        session.get.side_effect = [
            failing,
            self._response({"events": [_event(project="sentry-s4s2")]}),
        ]

        service = GcpServiceHealthService(["internal-sentry", "sentry-s4s2"])
        incidents = service.list_active_incidents()

        assert [i.event_id for i in incidents] == ["LDYWVWM"]
