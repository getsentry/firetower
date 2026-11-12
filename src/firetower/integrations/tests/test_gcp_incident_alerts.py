from datetime import UTC, datetime

from firetower.integrations.services.gcp_incident_alerts import (
    find_open_gcp_incidents,
    format_gcp_incidents_message,
    parse_gcp_incident_alert,
)

POLICY = "Emerging incidents"


def _gcp_alert(
    ts: str,
    event_id: str = "LDYWVWM",
    state: str = "ACTIVE",
    title: str = "VM to VM communication",
    policy: str = POLICY,
    project: str = "internal-sentry",
) -> dict:
    alert_url = (
        "https://console.cloud.google.com/monitoring/alerting/alerts/0.abc"
        f"?channelType=slack&amp;project={project}"
    )
    dashboard_url = (
        "https://console.cloud.google.com/servicehealth/eventDetails/"
        f"projects%2F123%2Flocations%2Fglobal%2Fevents%2F{event_id}"
    )
    text = (
        f"*<{alert_url}|{policy}>* Log match condition with labels "
        "{description=Google Engineers have confirmed an issue with Virtual "
        "Private Cloud (VPC).\n\n,impactedLocations=['us-east1', 'us-south1'],"
        "impactedProducts=['Virtual Private Cloud (VPC)'],"
        f"startTime=2026-11-12T07:48:02Z,state={state},title={title}}} fired for "
        f"Event with {{event_id={event_id}, location=global, resource_container=123}}. "
        "Alert status Alert open No severity *Documentation* ### "
        f"{title}\nCheck out <{dashboard_url}|Personalized Service Health dashboard> "
        f"for more details. *<{alert_url}|View alert>*"
    )
    return {"type": "message", "ts": ts, "text": text, "bot_id": "B0GCP"}


def _snapshot_alert(ts: str) -> dict:
    return {
        "type": "message",
        "ts": ts,
        "text": (
            "*<https://console.cloud.google.com/monitoring/alerting/alerts/0.x"
            "|Attn: @here (us) No GCP scheduled disk snapshot log detected>* "
            "The metric logging/user/ops.snapshot.disk.done has not been seen."
        ),
    }


class TestParseGcpIncidentAlert:
    def test_parses_service_health_alert(self):
        alert = parse_gcp_incident_alert(_gcp_alert("100.1"), POLICY)

        assert alert is not None
        assert alert.event_id == "LDYWVWM"
        assert alert.title == "VM to VM communication"
        assert alert.state == "ACTIVE"
        assert alert.products == ["Virtual Private Cloud (VPC)"]
        assert alert.locations == ["us-east1", "us-south1"]
        assert alert.start_time == datetime(2026, 11, 12, 7, 48, 2, tzinfo=UTC)
        assert alert.message_ts == "100.1"
        assert alert.dashboard_url is not None
        assert alert.dashboard_url.endswith("events%2FLDYWVWM")
        assert "channelType=slack&project=internal-sentry" in alert.alert_url

    def test_ignores_other_alert_policies(self):
        assert parse_gcp_incident_alert(_snapshot_alert("100.1"), POLICY) is None

    def test_ignores_message_without_event_id(self):
        message = {
            "ts": "100.1",
            "text": "*<https://console.cloud.google.com/x|Emerging incidents>* hi",
        }
        assert parse_gcp_incident_alert(message, POLICY) is None

    def test_ignores_message_without_text(self):
        assert parse_gcp_incident_alert({"ts": "100.1"}, POLICY) is None

    def test_unescapes_title(self):
        alert = parse_gcp_incident_alert(
            _gcp_alert("100.1", title="GCS &amp; BigQuery errors"), POLICY
        )
        assert alert is not None
        assert alert.title == "GCS & BigQuery errors"


class TestFindOpenGcpIncidents:
    def test_dedupes_by_event_keeping_newest(self):
        messages = [
            _gcp_alert("300.0", event_id="AAA", project="sentry-s4s2"),
            _gcp_alert("200.0", event_id="AAA"),
            _gcp_alert("100.0", event_id="BBB", title="Cloud SQL latency"),
            _snapshot_alert("150.0"),
        ]

        alerts = find_open_gcp_incidents(messages, POLICY)

        assert [(a.event_id, a.message_ts) for a in alerts] == [
            ("AAA", "300.0"),
            ("BBB", "100.0"),
        ]

    def test_skips_events_whose_latest_update_is_closed(self):
        messages = [
            _gcp_alert("200.0", event_id="AAA", state="CLOSED"),
            _gcp_alert("100.0", event_id="AAA", state="ACTIVE"),
            _gcp_alert("150.0", event_id="BBB", state="ACTIVE"),
        ]

        alerts = find_open_gcp_incidents(messages, POLICY)

        assert [a.event_id for a in alerts] == ["BBB"]

    def test_returns_empty_when_no_matching_alerts(self):
        assert find_open_gcp_incidents([_snapshot_alert("1.0")], POLICY) == []


class TestFormatGcpIncidentsMessage:
    def test_formats_alert_lines(self):
        alert = parse_gcp_incident_alert(
            _gcp_alert("1794474114.449229", title="A <b> & c"), POLICY
        )
        assert alert is not None

        message = format_gcp_incidents_message(
            [alert], "C04671UFG9L", lambda ts: f"https://slack/p{ts}"
        )

        assert message.startswith(
            ":cloud: *Open GCP incidents that may be relevant* (from <#C04671UFG9L>):"
        )
        assert f"• <{alert.dashboard_url}|A &lt;b&gt; &amp; c>" in message
        assert "Virtual Private Cloud (VPC) in us-east1, us-south1" in message
        assert "(ACTIVE, started 2026-11-12 07:48 UTC)" in message
        assert "<https://slack/p1794474114.449229|alert>" in message
