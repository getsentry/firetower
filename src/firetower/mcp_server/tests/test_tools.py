"""Tests that the read-only tools call the SDK correctly (Hop 2 mocked)."""

from unittest.mock import MagicMock

import pytest

from firetower.mcp_server import firetower, tools


@pytest.fixture(autouse=True)
def _bypass_gate(monkeypatch):
    monkeypatch.setattr(tools, "require_sentry_account", lambda: None)


def test_get_incident_calls_sdk(monkeypatch):
    client = MagicMock()
    client.get_incident.return_value = {"id": "INC-2000"}
    monkeypatch.setattr(firetower, "get_client", lambda: client)

    assert tools.get_incident("INC-2000") == {"id": "INC-2000"}
    client.get_incident.assert_called_once_with("INC-2000")


def test_list_incidents_forwards_filters(monkeypatch):
    client = MagicMock()
    client.list_incidents.return_value = {"count": 0, "results": []}
    monkeypatch.setattr(firetower, "get_client", lambda: client)

    tools.list_incidents(status=["Active"], severity=["P0"], page=2)
    kwargs = client.list_incidents.call_args.kwargs
    assert kwargs["statuses"] == ["Active"]
    assert kwargs["severities"] == ["P0"]
    assert kwargs["page"] == 2


def test_register_tools_registers_all():
    mcp = MagicMock()
    tools.register_tools(mcp)
    assert mcp.tool.call_count == len(tools.TOOLS)
