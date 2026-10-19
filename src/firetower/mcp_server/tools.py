"""Read-only MCP tools over firetower incident data.

Each tool runs the per-tool Sentry-account fallback gate, then reads through the
single service-identity ``FiretowerClient`` (Hop 2). Only methods exposed by
``firetower_sdk`` are wrapped — no raw endpoint access. The service account sees
only non-private incidents, so no tool can surface private data.
"""

import logging
import re
from collections.abc import Sequence
from typing import Annotated, Any, Literal, TypedDict, get_args

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from firetower_sdk.exceptions import FiretowerError
from mcp.types import ToolAnnotations
from pydantic import Field

from firetower.mcp_server import firetower
from firetower.mcp_server.auth import (
    requester_email,
    requester_subject,
    require_sentry_account,
)

logger = logging.getLogger(__name__)

IncidentStatusFilter = Literal["Active", "Mitigated", "Postmortem", "Done", "Canceled"]
IncidentSeverityFilter = Literal["P0", "P1", "P2", "P3", "P4"]
IncidentServiceTierFilter = Literal["T0", "T1", "T2", "T3", "T4"]
IncidentField = Literal[
    "id",
    "title",
    "description",
    "impact_summary",
    "status",
    "severity",
    "service_tier",
    "is_private",
    "captain",
    "reporter",
    "participants",
    "affected_service_tags",
    "affected_region_tags",
    "root_cause_tags",
    "impact_type_tags",
    "external_links",
    "created_at",
    "updated_at",
    "time_started",
    "time_detected",
    "time_analyzed",
    "time_mitigated",
    "time_recovered",
    "total_downtime",
]
IncidentDetailField = Literal[
    "id",
    "title",
    "description",
    "impact_summary",
    "status",
    "severity",
    "service_tier",
    "is_private",
    "captain",
    "reporter",
    "participants",
    "affected_service_tags",
    "affected_region_tags",
    "root_cause_tags",
    "impact_type_tags",
    "external_links",
    "created_at",
    "updated_at",
    "time_started",
    "time_detected",
    "time_analyzed",
    "time_mitigated",
    "time_recovered",
    "total_downtime",
    "action_items",
    "timeline",
]


class IncidentListResult(TypedDict):
    count: int
    page: int
    limit: int
    has_more: bool
    results: list[dict[str, Any]]


_INCIDENT_ID_PATTERN = re.compile(r"[A-Z][A-Z0-9]*-[0-9]+")
_INVALID_INCIDENT_ID_MESSAGE = "Invalid incident ID."
_DEFAULT_INCIDENT_LIMIT = 10
_MAX_INCIDENT_LIMIT = 100
_INVALID_INCIDENT_LIMIT_MESSAGE = f"limit must be between 1 and {_MAX_INCIDENT_LIMIT}."
_INVALID_INCIDENT_PAGE_MESSAGE = "page must be a positive integer."
_FIRETOWER_API_PAGE_SIZE = 50
_INCIDENT_FIELDS = frozenset(get_args(IncidentField))
_INCIDENT_DETAIL_FIELDS = frozenset(get_args(IncidentDetailField))
_READ_ONLY_TOOL_ANNOTATIONS = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
)


def _audit(tool: str, **params: Any) -> None:
    """Per-user audit trail: who called which tool with what filters. firetower's
    own logs only see the shared service account, so this is where attribution lives.
    """
    active = {k: v for k, v in params.items() if v is not None}
    logger.info(
        "MCP tool call",
        extra={
            "event": "mcp_tool_call",
            "actor_email": requester_email(),
            "actor_sub": requester_subject(),
            "tool": tool,
            "params": active,
        },
    )


def _validate_fields(
    fields: Sequence[str] | None,
    allowed_fields: frozenset[str] = _INCIDENT_FIELDS,
) -> None:
    if fields is None:
        return
    if not fields:
        raise ToolError("fields must contain at least one incident field.")
    unknown_fields = set(fields) - allowed_fields
    if unknown_fields:
        unknown = ", ".join(sorted(unknown_fields))
        raise ToolError(f"Unknown incident field(s): {unknown}.")


def _project_incident(
    incident: dict[str, Any], fields: Sequence[str] | None
) -> dict[str, Any]:
    if fields is None:
        return incident
    return {field: incident[field] for field in fields}


def _sanitized(action: str, error: FiretowerError) -> ToolError:
    """Log the raw upstream error but return a generic message to the client.

    Keep both client responses and MCP logs generic even if a future SDK change
    adds upstream details to ``FiretowerError``. Map common statuses to friendly text.
    """
    logger.info(
        "Firetower API request failed",
        extra={
            "event": "firetower_api_error",
            "action": action,
            "status_code": error.status_code,
        },
    )
    if error.status_code in (401, 403, 404):
        return ToolError(f"Could not {action}: not found or not accessible.")
    return ToolError(f"Could not {action}: the firetower API is unavailable.")


def list_incidents(
    status: list[IncidentStatusFilter] | None = None,
    severity: list[IncidentSeverityFilter] | None = None,
    service_tier: list[IncidentServiceTierFilter] | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    affected_service: list[str] | None = None,
    root_cause: list[str] | None = None,
    impact_type: list[str] | None = None,
    affected_region: list[str] | None = None,
    captain: list[str] | None = None,
    reporter: list[str] | None = None,
    participant: list[str] | None = None,
    fields: Annotated[list[IncidentField], Field(min_length=1)] | None = None,
    page: Annotated[int, Field(ge=1)] = 1,
    limit: Annotated[int, Field(ge=1, le=_MAX_INCIDENT_LIMIT)] = (
        _DEFAULT_INCIDENT_LIMIT
    ),
) -> IncidentListResult:
    """List incidents with optional filters. Use to find incidents matching a
    status, severity, service tier, date range, tag, captain, reporter, or participant.

    Valid values (pass exactly, case-sensitive):
      status: "Active", "Mitigated", "Postmortem", "Done", "Canceled"
      severity: "P0", "P1", "P2", "P3", "P4"
      service_tier: "T0", "T1", "T2", "T3", "T4"

    Dates are ISO 8601. Each tag/email filter is a list (OR within a filter);
    put each value in its own list element, not comma-separated. The newest 10
    matching incidents are returned by default; pass ``limit`` up to 100 to
    control the return size. ``page`` uses that limit as its page size, so page 2 returns
    the next ``limit`` matching incidents. Responses contain ``count``,
    ``page``, ``limit``, ``has_more``, and ``results``. When ``has_more`` is
    true, request ``page + 1`` with the same filters, fields, and limit.

    Always pass ``fields`` with only the fields needed for the task to minimize
    context usage. For discovery, prefer ``["id", "title", "status",
    "severity"]`` and add fields only when needed. Omit ``fields`` only when
    full incident records are explicitly required. For full details about one
    known incident, use ``get_incident`` instead of relisting full records.

    Valid fields are: id, title, description,
    impact_summary, status, severity, service_tier, is_private, captain,
    reporter, participants, affected_service_tags, affected_region_tags,
    root_cause_tags, impact_type_tags, external_links, created_at, updated_at,
    time_started, time_detected, time_analyzed, time_mitigated, time_recovered,
    and total_downtime."""
    require_sentry_account()
    if page < 1:
        raise ToolError(_INVALID_INCIDENT_PAGE_MESSAGE)
    if not 1 <= limit <= _MAX_INCIDENT_LIMIT:
        raise ToolError(_INVALID_INCIDENT_LIMIT_MESSAGE)
    _validate_fields(fields)
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
        participant=participant,
        fields=fields,
        page=page,
        limit=limit,
    )
    try:
        client = firetower.get_client()
        filters: dict[str, Any] = {
            "statuses": status,
            "severities": severity,
            "service_tiers": service_tier,
            "created_after": created_after,
            "created_before": created_before,
            "affected_service": affected_service,
            "root_cause": root_cause,
            "impact_type": impact_type,
            "affected_region": affected_region,
            "captain": captain,
            "reporter": reporter,
            "participant": participant,
        }
        offset = (page - 1) * limit
        api_page = offset // _FIRETOWER_API_PAGE_SIZE + 1
        start_index = offset % _FIRETOWER_API_PAGE_SIZE
        response = client.list_incidents(**filters, page=api_page)
        count = response["count"]
        results = list(response["results"])
        current_api_page = api_page

        while len(results) < start_index + limit and isinstance(
            response.get("next"), str
        ):
            current_api_page += 1
            response = client.list_incidents(**filters, page=current_api_page)
            page_results = list(response["results"])
            if not page_results:
                break
            results.extend(page_results)

        results = results[start_index : start_index + limit]
        projected_results = [
            _project_incident(incident, fields) for incident in results
        ]
        return {
            "count": count,
            "page": page,
            "limit": limit,
            "has_more": offset + len(results) < count,
            "results": projected_results,
        }
    except FiretowerError as exc:
        raise _sanitized("list incidents", exc) from exc


def get_incident(
    incident_id: str,
    fields: Annotated[list[IncidentDetailField], Field(min_length=1)] | None = None,
) -> dict[str, Any]:
    """Get an incident by id (e.g. "INC-2000"), including participants, tags,
    external links, timeline milestones, action items, and timeline events. Pass
    ``fields`` with only the fields needed for the task to minimize context
    usage. Request ``action_items`` to return all action items in their display
    order, or ``timeline`` to return all events in chronological order. Omit
    ``fields`` only when the full incident record is explicitly required."""
    require_sentry_account()
    if _INCIDENT_ID_PATTERN.fullmatch(incident_id) is None:
        raise ToolError(_INVALID_INCIDENT_ID_MESSAGE)
    _validate_fields(fields, _INCIDENT_DETAIL_FIELDS)
    _audit("get_incident", incident_id=incident_id, fields=fields)
    try:
        client = firetower.get_client()
        incident = client.get_incident(incident_id)
        if fields is None or "action_items" in fields:
            incident["action_items"] = client.get_incident_action_items(incident_id)
        if fields is None or "timeline" in fields:
            incident["timeline"] = client.get_incident_timeline(incident_id)
        return _project_incident(incident, fields)
    except FiretowerError as exc:
        raise _sanitized("get incident", exc) from exc


TOOLS = (list_incidents, get_incident)


def register_tools(mcp: FastMCP) -> None:
    for tool in TOOLS:
        mcp.tool(tool, annotations=_READ_ONLY_TOOL_ANNOTATIONS)
