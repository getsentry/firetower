"""Tests that the read-only tools call the SDK correctly (Hop 2 mocked)."""

import re
from unittest.mock import MagicMock

import pytest
from fastmcp.exceptions import ToolError
from firetower_sdk.exceptions import FiretowerError

from firetower.mcp_server import firetower, tools


@pytest.fixture
def gate_spy(monkeypatch):
    """Replace the Sentry-account gate with a no-op spy so we can assert it ran."""
    spy = MagicMock()
    monkeypatch.setattr(tools, "require_sentry_account", spy)
    return spy


@pytest.mark.parametrize("incident_id", ["INC-2000", "TESTINC-2239"])
def test_get_incident_calls_sdk(monkeypatch, gate_spy, incident_id):
    client = MagicMock()
    client.get_incident.return_value = {"id": incident_id}
    monkeypatch.setattr(firetower, "get_client", lambda: client)

    assert tools.get_incident(incident_id) == {"id": incident_id}
    client.get_incident.assert_called_once_with(incident_id)


@pytest.mark.parametrize(
    "incident_id",
    [
        "../INC-2000",
        "INC-2000/details",
        r"INC-2000\details",
        "INC-2000?view=full",
        "INC-2000#timeline",
        "INC%2D2000",
        " INC-2000",
        "INC-2000\n",
        "inc-2000",
    ],
)
def test_get_incident_rejects_invalid_ids_before_audit_or_sdk(
    monkeypatch, gate_spy, incident_id
):
    audit = MagicMock()
    get_client = MagicMock()
    monkeypatch.setattr(tools, "_audit", audit)
    monkeypatch.setattr(firetower, "get_client", get_client)

    with pytest.raises(ToolError, match=r"^Invalid incident ID\.$"):
        tools.get_incident(incident_id)

    gate_spy.assert_called_once_with()
    audit.assert_not_called()
    get_client.assert_not_called()


def test_list_incidents_forwards_filters(monkeypatch, gate_spy):
    client = MagicMock()
    client.list_incidents.return_value = {"count": 0, "results": []}
    monkeypatch.setattr(firetower, "get_client", lambda: client)

    tools.list_incidents(
        status=["Active"],
        severity=["P0"],
        service_tier=["T0"],
        created_after="2026-01-01",
        created_before="2026-02-01",
        affected_service=["api"],
        root_cause=["bug"],
        impact_type=["latency"],
        affected_region=["us"],
        captain=["a@sentry.io"],
        reporter=["b@sentry.io"],
        participant=["c@sentry.io"],
        page=2,
    )
    kwargs = client.list_incidents.call_args.kwargs
    # The tool renames the public params to the SDK's plural names.
    assert kwargs["statuses"] == ["Active"]
    assert kwargs["severities"] == ["P0"]
    assert kwargs["service_tiers"] == ["T0"]
    assert kwargs["created_after"] == "2026-01-01"
    assert kwargs["created_before"] == "2026-02-01"
    assert kwargs["affected_service"] == ["api"]
    assert kwargs["root_cause"] == ["bug"]
    assert kwargs["impact_type"] == ["latency"]
    assert kwargs["affected_region"] == ["us"]
    assert kwargs["captain"] == ["a@sentry.io"]
    assert kwargs["reporter"] == ["b@sentry.io"]
    assert kwargs["participant"] == ["c@sentry.io"]
    assert kwargs["page"] == 2


@pytest.mark.parametrize(
    ("kwargs", "expected_count"),
    [
        ({}, 10),
        ({"limit": 3}, 3),
        ({"limit": 50}, 15),
    ],
)
def test_list_incidents_limits_results(monkeypatch, gate_spy, kwargs, expected_count):
    incidents = [{"id": f"INC-{number}"} for number in range(15, 0, -1)]
    client = MagicMock()
    client.list_incidents.return_value = {
        "count": len(incidents),
        "next": None,
        "previous": None,
        "results": incidents,
    }
    monkeypatch.setattr(firetower, "get_client", lambda: client)

    response = tools.list_incidents(**kwargs)

    assert response["count"] == len(incidents)
    assert response["results"] == incidents[:expected_count]


def test_list_incidents_projects_selected_fields(monkeypatch, gate_spy):
    client = MagicMock()
    client.list_incidents.return_value = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": "INC-2000",
                "title": "An incident",
                "captain": "captain@sentry.io",
                "severity": "P1",
                "description": "Unneeded context",
            }
        ],
    }
    monkeypatch.setattr(firetower, "get_client", lambda: client)

    response = tools.list_incidents(fields=["id", "captain", "severity"], limit=50)

    assert response["results"] == [
        {
            "id": "INC-2000",
            "captain": "captain@sentry.io",
            "severity": "P1",
        }
    ]


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ([], "fields must contain at least one incident field."),
        (["id", "unknown"], "Unknown incident field(s): unknown."),
    ],
)
def test_list_incidents_rejects_invalid_fields_before_audit_or_sdk(
    monkeypatch, gate_spy, fields, message
):
    audit = MagicMock()
    get_client = MagicMock()
    monkeypatch.setattr(tools, "_audit", audit)
    monkeypatch.setattr(firetower, "get_client", get_client)

    with pytest.raises(ToolError, match=rf"^{re.escape(message)}$"):
        tools.list_incidents(fields=fields)

    gate_spy.assert_called_once_with()
    audit.assert_not_called()
    get_client.assert_not_called()


def test_list_incidents_fetches_additional_pages_for_large_limit(monkeypatch, gate_spy):
    incidents = [{"id": f"INC-{number}"} for number in range(100, 0, -1)]
    client = MagicMock()
    client.list_incidents.side_effect = [
        {
            "count": len(incidents),
            "next": "https://firetower.example/api/incidents/?page=2",
            "previous": None,
            "results": incidents[:50],
        },
        {
            "count": len(incidents),
            "next": None,
            "previous": "https://firetower.example/api/incidents/?page=1",
            "results": incidents[50:],
        },
    ]
    monkeypatch.setattr(firetower, "get_client", lambda: client)

    response = tools.list_incidents(limit=75)

    assert response["results"] == incidents[:75]
    assert client.list_incidents.call_count == 2
    assert client.list_incidents.call_args_list[0].kwargs["page"] == 1
    assert client.list_incidents.call_args_list[1].kwargs["page"] == 2


@pytest.mark.parametrize("limit", [0, -1])
def test_list_incidents_rejects_invalid_limit_before_audit_or_sdk(
    monkeypatch, gate_spy, limit
):
    audit = MagicMock()
    get_client = MagicMock()
    monkeypatch.setattr(tools, "_audit", audit)
    monkeypatch.setattr(firetower, "get_client", get_client)

    with pytest.raises(ToolError, match=r"^limit must be a positive integer\.$"):
        tools.list_incidents(limit=limit)

    gate_spy.assert_called_once_with()
    audit.assert_not_called()
    get_client.assert_not_called()


@pytest.mark.parametrize(
    "call",
    [
        lambda: tools.get_incident("INC-2000"),
        lambda: tools.list_incidents(),
    ],
)
def test_tools_invoke_gate(monkeypatch, gate_spy, call):
    # Deleting the require_sentry_account() call in a tool must fail this test.
    monkeypatch.setattr(firetower, "get_client", lambda: MagicMock())
    call()
    gate_spy.assert_called_once_with()


@pytest.mark.parametrize("status_code", [401, 403, 404, 500, None])
def test_get_incident_sanitizes_errors(monkeypatch, gate_spy, status_code):
    client = MagicMock()
    client.get_incident.side_effect = FiretowerError(
        "Firetower API error (404): {secret IAP/Django body}",
        status_code=status_code,
    )
    monkeypatch.setattr(firetower, "get_client", lambda: client)

    with pytest.raises(ToolError) as exc:
        tools.get_incident("INC-2000")
    # The raw upstream body must NOT leak to the client.
    assert "IAP" not in str(exc.value)
    assert "Django" not in str(exc.value)
    assert "secret" not in str(exc.value)


def test_list_incidents_sanitizes_errors(monkeypatch, gate_spy):
    client = MagicMock()
    client.list_incidents.side_effect = FiretowerError(
        "Firetower API error (403): {raw body}", status_code=403
    )
    monkeypatch.setattr(firetower, "get_client", lambda: client)

    with pytest.raises(ToolError) as exc:
        tools.list_incidents()
    assert "raw body" not in str(exc.value)


def test_register_tools_registers_all():
    mcp = MagicMock()
    tools.register_tools(mcp)
    assert mcp.tool.call_count == len(tools.TOOLS)
