"""Read-only MCP tools over firetower incident data.

Each tool runs the per-tool Sentry-account fallback gate, then reads through the
single service-identity ``FiretowerClient`` (Hop 2). Only methods exposed by
``firetower_sdk`` are wrapped — no raw endpoint access. The service account sees
only non-private incidents, so no tool can surface private data.
"""

from typing import Any

from fastmcp import FastMCP

from firetower.mcp_server import firetower
from firetower.mcp_server.auth import require_sentry_account


def list_incidents(
    status: list[str] | None = None,
    severity: list[str] | None = None,
    service_tier: list[str] | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    affected_service: list[str] | None = None,
    root_cause: list[str] | None = None,
    impact_type: list[str] | None = None,
    affected_region: list[str] | None = None,
    captain: list[str] | None = None,
    reporter: list[str] | None = None,
    page: int = 1,
) -> dict[str, Any]:
    """List incidents with optional filters. Use to find incidents matching a
    status, severity, service tier, date range, tag, captain, or reporter.
    Dates are ISO 8601. Each tag/email filter is a list (OR within a filter).
    Results are paginated; pass ``page`` to fetch more."""
    require_sentry_account()
    return firetower.get_client().list_incidents(
        statuses=status,
        severities=severity,
        service_tiers=service_tier,
        created_after=created_after,
        created_before=created_before,
        affected_service=affected_service,
        root_cause=root_cause,
        impact_type=impact_type,
        affected_region=affected_region,
        captain=captain,
        reporter=reporter,
        page=page,
    )


def get_incident(incident_id: str) -> dict[str, Any]:
    """Get full detail for a single incident by id (e.g. "INC-2000"), including
    participants, tags, external links, and timeline milestones."""
    require_sentry_account()
    return firetower.get_client().get_incident(incident_id)


TOOLS = (list_incidents, get_incident)


def register_tools(mcp: FastMCP) -> None:
    for tool in TOOLS:
        mcp.tool(tool)
