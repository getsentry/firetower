from datetime import datetime

from django.db.models import Q, QuerySet
from django.utils import timezone as django_timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from .models import Incident, IncidentSeverity, IncidentStatus, ServiceTier

EMPTY_FILTER_SENTINEL = "__empty__"


def parse_date_param(value: str) -> datetime | None:
    """Parse a date string from query params. Accepts ISO 8601 formats."""
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        # Try parsing as date-only (YYYY-MM-DD)
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
    if django_timezone.is_naive(dt):
        dt = django_timezone.make_aware(dt)
    return dt


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
    if "Any" in status_filters:
        return queryset
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
        include_empty = EMPTY_FILTER_SENTINEL in service_tier_filters
        tier_values = [v for v in service_tier_filters if v != EMPTY_FILTER_SENTINEL]
        if tier_values:
            valid_tiers = set(ServiceTier.__members__.values())
            invalid_tiers = set(tier_values) - valid_tiers
            if invalid_tiers:
                raise ValidationError(
                    {
                        "service_tier": f"Invalid service_tier value(s): {', '.join(invalid_tiers)}"
                    }
                )
        if include_empty and tier_values:
            queryset = queryset.filter(
                Q(service_tier__in=tier_values) | Q(service_tier__isnull=True)
            )
        elif include_empty:
            queryset = queryset.filter(service_tier__isnull=True)
        else:
            queryset = queryset.filter(service_tier__in=tier_values)
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
            include_empty = EMPTY_FILTER_SENTINEL in tag_names
            actual_tags = [v for v in tag_names if v != EMPTY_FILTER_SENTINEL]
            if include_empty and actual_tags:
                queryset = queryset.filter(
                    Q(**{f"{field_name}__name__in": actual_tags})
                    | Q(**{f"{field_name}__isnull": True})
                )
            elif include_empty:
                queryset = queryset.filter(**{f"{field_name}__isnull": True})
            else:
                queryset = queryset.filter(**{f"{field_name}__name__in": actual_tags})
            applied = True
    if applied:
        queryset = queryset.distinct()
    return queryset


def filter_by_captain(
    queryset: QuerySet[Incident], request: Request
) -> QuerySet[Incident]:
    captain_emails = request.GET.getlist("captain")
    if captain_emails:
        include_empty = EMPTY_FILTER_SENTINEL in captain_emails
        actual_emails = [v for v in captain_emails if v != EMPTY_FILTER_SENTINEL]
        if include_empty and actual_emails:
            queryset = queryset.filter(
                Q(captain__email__in=actual_emails) | Q(captain__isnull=True)
            )
        elif include_empty:
            queryset = queryset.filter(captain__isnull=True)
        else:
            queryset = queryset.filter(captain__email__in=actual_emails)
    return queryset


def filter_by_reporter(
    queryset: QuerySet[Incident], request: Request
) -> QuerySet[Incident]:
    reporter_emails = request.GET.getlist("reporter")
    if reporter_emails:
        include_empty = EMPTY_FILTER_SENTINEL in reporter_emails
        actual_emails = [v for v in reporter_emails if v != EMPTY_FILTER_SENTINEL]
        if include_empty and actual_emails:
            queryset = queryset.filter(
                Q(reporter__email__in=actual_emails) | Q(reporter__isnull=True)
            )
        elif include_empty:
            queryset = queryset.filter(reporter__isnull=True)
        else:
            queryset = queryset.filter(reporter__email__in=actual_emails)
    return queryset
