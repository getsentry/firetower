"""Read-only MCP tools over firetower incident data.

Each tool runs the per-tool Sentry-account fallback gate, then reads through the
single service-identity ``FiretowerClient`` (Hop 2). Only methods exposed by
``firetower_sdk`` are wrapped — no raw endpoint access. The service account sees
only non-private incidents, so no tool can surface private data.
"""

import logging
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from firetower_sdk.exceptions import FiretowerError

from firetower.mcp_server import firetower
from firetower.mcp_server.auth import requester_email, require_sentry_account

logger = logging.getLogger(__name__)


def _audit(tool: str, **params: Any) -> None:
    """Per-user audit trail: who called which tool with what filters. firetower's
    own logs only see the shared service account, so this is where attribution lives.
    """
    active = {k: v for k, v in params.items() if v is not None}
    logger.info(
        "mcp tool call: tool=%s user=%s params=%s", tool, requester_email(), active
    )


def _sanitized(action: str, error: FiretowerError) -> ToolError:
    """Log the raw upstream error but return a generic message to the client.

    ``FiretowerError`` messages embed the raw IAP/Django response body, which we
    must not echo back to the MCP client. Map common statuses to friendly text.
    """
    logger.info("Firetower %s failed: %s", action, error)
    if error.status_code in (401, 403, 404):
        return ToolError(f"Could not {action}: not found or not accessible.")
    return ToolError(f"Could not {action}: the firetower API is unavailable.")


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

    Valid values (pass exactly, case-sensitive):
      status: "Active", "Mitigated", "Postmortem", "Done", "Canceled"
      severity: "P0", "P1", "P2", "P3", "P4"
      service_tier: "T0", "T1", "T2", "T3", "T4"

    Dates are ISO 8601. Each tag/email filter is a list (OR within a filter);
    put each value in its own list element, not comma-separated. Results are
    paginated; pass ``page`` to fetch more."""
    require_sentry_account()
    _audit(
        "list_incidents",
        status=status,
        severity=severity,
        service_tier=service_tier,
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
    try:
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
    except FiretowerError as exc:
        raise _sanitized("list incidents", exc) from exc


def get_incident(incident_id: str) -> dict[str, Any]:
    """Get full detail for a single incident by id (e.g. "INC-2000"), including
    participants, tags, external links, and timeline milestones."""
    require_sentry_account()
    _audit("get_incident", incident_id=incident_id)
    try:
        return firetower.get_client().get_incident(incident_id)
    except FiretowerError as exc:
        raise _sanitized("get incident", exc) from exc


TOOLS = (list_incidents, get_incident)


def register_tools(mcp: FastMCP) -> None:
    for tool in TOOLS:
        mcp.tool(tool)
