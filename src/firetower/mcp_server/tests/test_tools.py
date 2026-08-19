"""Tests that the read-only tools call the SDK correctly (Hop 2 mocked)."""

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


def test_get_incident_calls_sdk(monkeypatch, gate_spy):
    client = MagicMock()
    client.get_incident.return_value = {"id": "INC-2000"}
    monkeypatch.setattr(firetower, "get_client", lambda: client)

    assert tools.get_incident("INC-2000") == {"id": "INC-2000"}
    client.get_incident.assert_called_once_with("INC-2000")


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
    assert kwargs["page"] == 2


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
