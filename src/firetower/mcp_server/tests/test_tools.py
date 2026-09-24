"""Tests that the read-only tools call the SDK correctly (Hop 2 mocked)."""

import asyncio
import re
from unittest.mock import MagicMock

import pytest
from django.conf import settings
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from firetower_sdk.exceptions import FiretowerError

from firetower.incidents.serializers import IncidentReadSerializer
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


def test_get_incident_projects_selected_fields(monkeypatch, gate_spy):
    client = MagicMock()
    client.get_incident.return_value = {
        "id": "INC-2000",
        "title": "An incident",
        "severity": "P1",
        "description": "Unneeded context",
    }
    monkeypatch.setattr(firetower, "get_client", lambda: client)

    response = tools.get_incident("INC-2000", fields=["id", "severity"])

    assert response == {"id": "INC-2000", "severity": "P1"}


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ([], "fields must contain at least one incident field."),
        (["id", "unknown"], "Unknown incident field(s): unknown."),
    ],
)
def test_get_incident_rejects_invalid_fields_before_audit_or_sdk(
    monkeypatch, gate_spy, fields, message
):
    audit = MagicMock()
    get_client = MagicMock()
    monkeypatch.setattr(tools, "_audit", audit)
    monkeypatch.setattr(firetower, "get_client", get_client)

    with pytest.raises(ToolError, match=rf"^{re.escape(message)}$"):
        tools.get_incident("INC-2000", fields=fields)

    gate_spy.assert_called_once_with()
    audit.assert_not_called()
    get_client.assert_not_called()


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
    assert kwargs["page"] == 1


@pytest.mark.parametrize(
    ("kwargs", "expected_count", "expected_limit", "expected_has_more"),
    [
        ({}, 10, 10, True),
        ({"limit": 3}, 3, 3, True),
        ({"limit": 50}, 15, 50, False),
    ],
)
def test_list_incidents_limits_results(
    monkeypatch,
    gate_spy,
    kwargs,
    expected_count,
    expected_limit,
    expected_has_more,
):
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

    assert response == {
        "count": len(incidents),
        "page": 1,
        "limit": expected_limit,
        "has_more": expected_has_more,
        "results": incidents[:expected_count],
    }


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


def test_list_incidents_uses_limit_sized_logical_pages(monkeypatch, gate_spy):
    incidents = [{"id": f"INC-{number}"} for number in range(100, 50, -1)]
    client = MagicMock()
    client.list_incidents.return_value = {
        "count": 100,
        "next": "https://firetower.example/api/incidents/?page=2",
        "previous": None,
        "results": incidents,
    }
    monkeypatch.setattr(firetower, "get_client", lambda: client)

    response = tools.list_incidents(page=2, limit=10, fields=["id"])

    assert response == {
        "count": 100,
        "page": 2,
        "limit": 10,
        "has_more": True,
        "results": incidents[10:20],
    }
    client.list_incidents.assert_called_once()
    assert client.list_incidents.call_args.kwargs["page"] == 1


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

    assert response == {
        "count": len(incidents),
        "page": 1,
        "limit": 75,
        "has_more": True,
        "results": incidents[:75],
    }
    assert "next" not in response
    assert "previous" not in response
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


@pytest.mark.parametrize("page", [0, -1])
def test_list_incidents_rejects_invalid_page_before_audit_or_sdk(
    monkeypatch, gate_spy, page
):
    audit = MagicMock()
    get_client = MagicMock()
    monkeypatch.setattr(tools, "_audit", audit)
    monkeypatch.setattr(firetower, "get_client", get_client)

    with pytest.raises(ToolError, match=r"^page must be a positive integer\.$"):
        tools.list_incidents(page=page)

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
    client = MagicMock()
    client.list_incidents.return_value = {"count": 0, "results": []}
    monkeypatch.setattr(firetower, "get_client", lambda: client)
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


def test_mcp_pagination_matches_firetower_api_page_size():
    assert tools._FIRETOWER_API_PAGE_SIZE == settings.REST_FRAMEWORK["PAGE_SIZE"]


def test_mcp_fields_match_service_api_serializer():
    assert tools._INCIDENT_FIELDS == frozenset(IncidentReadSerializer.Meta.fields)


def test_tool_schemas_expose_allowed_values_and_pagination_constraints():
    mcp = FastMCP("test")
    tools.register_tools(mcp)
    registered_tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
    list_tool = registered_tools["list_incidents"]
    list_properties = list_tool.parameters["properties"]
    detail_properties = registered_tools["get_incident"].parameters["properties"]

    def array_variant(property_schema):
        return next(
            variant
            for variant in property_schema["anyOf"]
            if variant.get("type") == "array"
        )

    assert set(array_variant(list_properties["status"])["items"]["enum"]) == {
        "Active",
        "Mitigated",
        "Postmortem",
        "Done",
        "Canceled",
    }
    assert set(array_variant(list_properties["severity"])["items"]["enum"]) == {
        "P0",
        "P1",
        "P2",
        "P3",
        "P4",
    }
    assert set(array_variant(list_properties["service_tier"])["items"]["enum"]) == {
        "T0",
        "T1",
        "T2",
        "T3",
        "T4",
    }
    expected_fields = set(tools._INCIDENT_FIELDS)
    assert set(array_variant(list_properties["fields"])["items"]["enum"]) == (
        expected_fields
    )
    assert set(array_variant(detail_properties["fields"])["items"]["enum"]) == (
        expected_fields
    )
    assert list_properties["page"]["minimum"] == 1
    assert list_properties["limit"]["minimum"] == 1

    assert list_tool.output_schema == {
        "properties": {
            "count": {"type": "integer"},
            "page": {"type": "integer"},
            "limit": {"type": "integer"},
            "has_more": {"type": "boolean"},
            "results": {
                "items": {"additionalProperties": True, "type": "object"},
                "type": "array",
            },
        },
        "required": ["count", "page", "limit", "has_more", "results"],
        "type": "object",
    }
    assert list_tool.description is not None
    assert "request ``page + 1``" in list_tool.description

    for tool in registered_tools.values():
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.idempotentHint is True
