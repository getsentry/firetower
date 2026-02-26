from datetime import datetime

from django.db.models import QuerySet
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from .models import Incident, IncidentSeverity, IncidentStatus, ServiceTier


def parse_date_param(value: str) -> datetime | None:
    """Parse a date string from query params. Accepts ISO 8601 formats."""
    if not value:
        return None
    dt = parse_datetime(value)
    if dt:
        return dt
    # Try parsing as date-only (YYYY-MM-DD)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def filter_by_date_range(
    queryset: QuerySet[Incident], request: Request
) -> QuerySet[Incident]:
    """Apply created_after and created_before filters to queryset."""
    created_after = request.GET.get("created_after")
    created_before = request.GET.get("created_before")

    if created_after:
        dt = parse_date_param(created_after)
        if dt is None:
            raise ValidationError(
                {
                    "created_after": "Invalid date format. Use ISO 8601 (e.g., 2024-01-15 or 2024-01-15T10:30:00Z)"
                }
            )
        queryset = queryset.filter(created_at__gte=dt)

    if created_before:
        dt = parse_date_param(created_before)
        if dt is None:
            raise ValidationError(
                {
                    "created_before": "Invalid date format. Use ISO 8601 (e.g., 2024-01-15 or 2024-01-15T10:30:00Z)"
                }
            )
        queryset = queryset.filter(created_at__lte=dt)

    return queryset


def filter_by_severity(
    queryset: QuerySet[Incident], request: Request
) -> QuerySet[Incident]:
    """Apply severity filter to queryset. Expects severity param in GET (can be repeated for multiple values)."""
    severity_filters = request.GET.getlist("severity")

    if severity_filters:
        valid_severities = set(IncidentSeverity.__members__.values())
        invalid_severities = set(severity_filters) - valid_severities

        if invalid_severities:
            raise ValidationError(
                {
                    "severity": f"Invalid severity value(s): {', '.join(invalid_severities)}"
                }
            )

        queryset = queryset.filter(severity__in=severity_filters)

    return queryset


def filter_by_status(
    queryset: QuerySet[Incident],
    request: Request,
    default: list[str] | None = None,
) -> QuerySet[Incident]:
    status_filters = request.GET.getlist("status")
    if not status_filters and default is not None:
        status_filters = default
    if status_filters:
        valid_statuses = set(IncidentStatus.__members__.values())
        invalid_statuses = set(status_filters) - valid_statuses
        if invalid_statuses:
            raise ValidationError(
                {"status": f"Invalid status value(s): {', '.join(invalid_statuses)}"}
            )
        queryset = queryset.filter(status__in=status_filters)
    return queryset


def filter_by_service_tier(
    queryset: QuerySet[Incident], request: Request
) -> QuerySet[Incident]:
    service_tier_filters = request.GET.getlist("service_tier")
    if service_tier_filters:
        valid_tiers = set(ServiceTier.__members__.values())
        invalid_tiers = set(service_tier_filters) - valid_tiers
        if invalid_tiers:
            raise ValidationError(
                {
                    "service_tier": f"Invalid service_tier value(s): {', '.join(invalid_tiers)}"
                }
            )
        queryset = queryset.filter(service_tier__in=service_tier_filters)
    return queryset


TAG_FILTER_PARAMS = {
    "affected_service": "affected_service_tags",
    "root_cause": "root_cause_tags",
    "impact_type": "impact_type_tags",
    "affected_region": "affected_region_tags",
}


def filter_by_tags(
    queryset: QuerySet[Incident], request: Request
) -> QuerySet[Incident]:
    applied = False
    for param_name, field_name in TAG_FILTER_PARAMS.items():
        tag_names = request.GET.getlist(param_name)
        if tag_names:
            queryset = queryset.filter(**{f"{field_name}__name__in": tag_names})
            applied = True
    if applied:
        queryset = queryset.distinct()
    return queryset


def filter_by_captain(
    queryset: QuerySet[Incident], request: Request
) -> QuerySet[Incident]:
    captain_emails = request.GET.getlist("captain")
    if captain_emails:
        queryset = queryset.filter(captain__email__in=captain_emails)
    return queryset


def filter_by_reporter(
    queryset: QuerySet[Incident], request: Request
) -> QuerySet[Incident]:
    reporter_emails = request.GET.getlist("reporter")
    if reporter_emails:
        queryset = queryset.filter(reporter__email__in=reporter_emails)
    return queryset
