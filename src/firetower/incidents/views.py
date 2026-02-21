import calendar
import logging
import re
from dataclasses import asdict
from datetime import datetime
from datetime import tzinfo as TzInfo

from django.conf import settings
from django.db.models import Count, QuerySet, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    INCIDENT_ID_START,
    Incident,
    IncidentOrRedirect,
    IncidentSeverity,
    Tag,
    TagType,
    filter_visible_to_user,
)
from .permissions import IncidentPermission
from .serializers import (
    IncidentListUISerializer,
    IncidentOrRedirectReadSerializer,
    IncidentReadSerializer,
    IncidentWriteSerializer,
    TagCreateSerializer,
    TagSerializer,
)
from .services import ParticipantsSyncStats, sync_incident_participants_from_slack

logger = logging.getLogger(__name__)


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


class IncidentListUIView(generics.ListAPIView):
    """
    List all incidents from database.

    Supports:
    - Pagination (configured in settings.REST_FRAMEWORK)
    - Status filtering via query params: ?status=Active&status=Mitigated
      (defaults to Active and Mitigated if no status param provided)
    - Date filtering: ?created_after=2024-01-15&created_before=2024-01-31
    - Privacy: users only see public incidents + their own private incidents

    Authentication enforced via DEFAULT_PERMISSION_CLASSES in settings.
    """

    serializer_class = IncidentListUISerializer

    def get_queryset(self) -> QuerySet[Incident]:
        """Filter incidents by visibility, status, severity, and date range"""
        queryset = Incident.objects.all()
        queryset = filter_visible_to_user(queryset, self.request.user)

        # Filter by status (defaults to Active and Mitigated if not specified)
        status_filters = self.request.GET.getlist("status")
        if not status_filters:
            status_filters = ["Active", "Mitigated"]
        queryset = queryset.filter(status__in=status_filters)

        # Filter by severity
        queryset = filter_by_severity(queryset, self.request)

        # Filter by date range
        queryset = filter_by_date_range(queryset, self.request)

        return queryset


class IncidentDetailUIView(generics.RetrieveAPIView):
    """
    Get specific incident details from database.

    Accepts incident_id in format: INC-2000
    Returns 404 if incident not found or user doesn't have access.
    Uses prefetch_related for optimized queries.

    Authentication enforced via DEFAULT_PERMISSION_CLASSES in settings.
    """

    serializer_class = IncidentOrRedirectReadSerializer
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[Incident]:
        """Get base queryset with optimized prefetching"""
        return Incident.objects.prefetch_related(
            "captain__userprofile",
            "reporter__userprofile",
            "participants__userprofile",
            "affected_service_tags",
            "affected_region_tags",
            "root_cause_tags",
            "impact_type_tags",
            "external_links",
        )

    def get_object(self) -> IncidentOrRedirect:
        """
        Parse INC-2000 format and filter by visibility.

        Returns incident if found and user has access, otherwise 404.
        """
        incident_id = self.kwargs["incident_id"]
        project_key = settings.PROJECT_KEY

        # Extract numeric ID from incident number (INC-2000 -> 2000), case-insensitive
        incident_pattern = rf"^{re.escape(project_key)}-(\d+)$"
        match = re.match(incident_pattern, incident_id, re.IGNORECASE)

        if not match:
            raise ValidationError(
                f"Invalid incident ID format. Expected format: {project_key}-<number> (e.g., {project_key}-123)"
            )

        numeric_id = int(match.group(1))
        if numeric_id < INCIDENT_ID_START:
            return IncidentOrRedirect(
                redirect=f"{settings.JIRA['DOMAIN']}/browse/{project_key}-{numeric_id}"
            )

        # Get incident by numeric ID
        queryset = self.get_queryset()
        queryset = filter_visible_to_user(queryset, self.request.user)

        incident = get_object_or_404(queryset, id=numeric_id)

        try:
            sync_incident_participants_from_slack(incident)
        except Exception as e:
            logger.error(
                f"Failed to sync participants for incident {incident.id}: {e}",
                exc_info=True,
            )

        return IncidentOrRedirect(incident=incident)


# View aliases for cleaner URL imports
incident_list_ui = IncidentListUIView.as_view()
incident_detail_ui = IncidentDetailUIView.as_view()


class IncidentListCreateAPIView(generics.ListCreateAPIView):
    """
    Service API for listing and creating incidents.

    GET: List all incidents visible to the user
         Supports date filtering: ?created_after=2024-01-15&created_before=2024-01-31
    POST: Create a new incident

    Uses IncidentPermission for access control.
    """

    permission_classes = [IncidentPermission]

    def get_serializer_class(self) -> type[serializers.Serializer]:
        """Use different serializers for list vs create"""
        if self.request.method == "POST":
            return IncidentWriteSerializer
        return IncidentReadSerializer

    def get_queryset(self) -> QuerySet[Incident]:
        """Filter incidents by visibility, severity, and date range"""
        queryset = Incident.objects.all()
        queryset = filter_visible_to_user(queryset, self.request.user)
        queryset = filter_by_severity(queryset, self.request)
        queryset = filter_by_date_range(queryset, self.request)
        return queryset


class IncidentRetrieveUpdateAPIView(generics.RetrieveUpdateAPIView):
    """
    Service API for retrieving and updating incidents.

    GET: Get incident details
    PATCH: Partial update

    Accepts incident_id in format: INC-2000
    Uses IncidentPermission for access control.
    """

    permission_classes = [IncidentPermission]
    lookup_field = "id"
    http_method_names = ["get", "patch", "options", "head"]

    def get_serializer_class(self) -> type[serializers.Serializer]:
        """Use different serializers for retrieve vs update"""
        if self.request.method == "GET":
            return IncidentReadSerializer
        return IncidentWriteSerializer

    def get_queryset(self) -> QuerySet[Incident]:
        """Get base queryset with optimized prefetching"""
        return Incident.objects.prefetch_related(
            "captain__userprofile",
            "reporter__userprofile",
            "participants__userprofile",
            "affected_service_tags",
            "affected_region_tags",
            "root_cause_tags",
            "impact_type_tags",
            "external_links",
        )

    def get_object(self) -> Incident:
        """
        Parse INC-2000 format and check permissions.

        Returns incident if found and user has access, otherwise 404.
        Filters by visibility before lookup to avoid leaking incident existence.
        """
        incident_id = self.kwargs["incident_id"]
        project_key = settings.PROJECT_KEY

        # Extract numeric ID from incident number (INC-2000 -> 2000), case-insensitive
        incident_pattern = rf"^{re.escape(project_key)}-(\d+)$"
        match = re.match(incident_pattern, incident_id, re.IGNORECASE)

        if not match:
            raise ValidationError(
                f"Invalid incident ID format. Expected format: {project_key}-<number> (e.g., {project_key}-123)"
            )

        # Get incident by numeric ID, filtered by visibility
        numeric_id = int(match.group(1))
        queryset = self.get_queryset()

        # Filter by visibility before lookup (404 if not visible)
        queryset = filter_visible_to_user(queryset, self.request.user)

        # Get the incident (404 if not found OR not visible)
        obj = get_object_or_404(queryset, id=numeric_id)

        # Check object permissions for write operations
        self.check_object_permissions(self.request, obj)

        try:
            sync_incident_participants_from_slack(obj)
        except Exception as e:
            logger.error(
                f"Failed to sync participants for incident {obj.id}: {e}",
                exc_info=True,
            )

        return obj


class SyncIncidentParticipantsView(generics.GenericAPIView):
    """
    Force sync incident participants from Slack channel.

    POST /api/incidents/{incident_id}/sync-participants/

    Accepts incident_id in format: INC-2000
    Returns sync statistics.
    Bypasses throttle (force=True).

    Uses IncidentPermission for access control.
    """

    permission_classes = [IncidentPermission]

    def get_queryset(self) -> QuerySet[Incident]:
        return Incident.objects.all()

    def get_object(self) -> Incident:
        """
        Parse INC-2000 format and check permissions.

        Returns incident if found and user has access, otherwise 404.
        """
        incident_id = self.kwargs["incident_id"]
        project_key = settings.PROJECT_KEY

        # Case-insensitive match for incident ID format
        incident_pattern = rf"^{re.escape(project_key)}-(\d+)$"
        match = re.match(incident_pattern, incident_id, re.IGNORECASE)

        if not match:
            raise ValidationError(
                f"Invalid incident ID format. Expected format: {project_key}-<number> (e.g., {project_key}-123)"
            )

        numeric_id = int(match.group(1))
        queryset = self.get_queryset()
        queryset = filter_visible_to_user(queryset, self.request.user)

        obj = get_object_or_404(queryset, id=numeric_id)

        # Check object permissions
        self.check_object_permissions(self.request, obj)

        return obj

    def post(self, request: Request, incident_id: str) -> Response:
        incident = self.get_object()

        try:
            stats = sync_incident_participants_from_slack(incident, force=True)
            return Response({"success": True, "stats": asdict(stats)})
        except Exception as e:
            logger.error(
                f"Failed to force sync participants for incident {incident.id}: {e}",
                exc_info=True,
            )
            error_stats = ParticipantsSyncStats(
                errors=["Failed to sync participants from Slack"]
            )
            return Response(
                {
                    "success": False,
                    "error": "Failed to sync participants from Slack",
                    "stats": asdict(error_stats),
                },
                status=500,
            )


# View alias for sync endpoint
sync_incident_participants = SyncIncidentParticipantsView.as_view()


class TagListCreateAPIView(generics.ListCreateAPIView):
    """
    List or create tags.

    GET /api/tags/?type=AFFECTED_SERVICE
    GET /api/tags/?type=AFFECTED_REGION
    GET /api/tags/?type=ROOT_CAUSE
    GET /api/tags/?type=IMPACT_TYPE
    POST /api/tags/

    GET returns all tags filtered by type. The type query parameter is required.
    POST creates a new tag with name and type in the request body.
    """

    pagination_class = None

    def get_serializer_class(self) -> type[serializers.Serializer]:
        if self.request.method == "POST":
            return TagCreateSerializer
        return TagSerializer

    def get_queryset(self) -> QuerySet[Tag]:
        tag_type = self.request.GET.get("type")

        if not tag_type:
            raise ValidationError("type query parameter is required")

        if tag_type not in TagType.values:
            raise ValidationError(
                f"Invalid type '{tag_type}'. Must be one of: {', '.join(TagType.values)}"
            )

        related_name_map = {
            "AFFECTED_SERVICE": "incidents_by_affected_service",
            "ROOT_CAUSE": "incidents_by_root_cause",
            "IMPACT_TYPE": "incidents_by_impact_type",
            "AFFECTED_REGION": "incidents_by_affected_region",
        }
        related_name = related_name_map[tag_type]

        return (
            Tag.objects.filter(type=tag_type)
            .annotate(usage_count=Count(related_name))
            .order_by("-usage_count", "name")
        )


# ─── Availability helpers ─────────────────────────────────────────────────────

_HISTORY_MONTHS = 12
_HISTORY_QUARTERS = 8
_HISTORY_YEARS = 3


def _format_downtime(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    if minutes == 0:
        return "0m"
    hours = minutes // 60
    mins = minutes % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if mins > 0:
        parts.append(f"{mins}m")
    return " ".join(parts)


def _get_month_periods(now: datetime) -> list[dict]:
    periods = []
    year, month = now.year, now.month
    for _ in range(_HISTORY_MONTHS):
        last_day = calendar.monthrange(year, month)[1]
        start = now.replace(
            year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        end = now.replace(
            year=year,
            month=month,
            day=last_day,
            hour=23,
            minute=59,
            second=59,
            microsecond=999999,
        )
        label = start.strftime("%B %Y")
        periods.append({"label": label, "start": start, "end": end})
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return periods


def _current_fiscal_quarter(now: datetime) -> tuple[int, int]:
    m = now.month
    if m == 1:
        return now.year - 1, 4
    elif m <= 4:
        return now.year, 1
    elif m <= 7:
        return now.year, 2
    elif m <= 10:
        return now.year, 3
    return now.year, 4


def _prev_fiscal_quarter(fy_year: int, quarter: int) -> tuple[int, int]:
    if quarter == 1:
        return fy_year - 1, 4
    return fy_year, quarter - 1


def _get_fiscal_quarter_bounds(
    fy_year: int, quarter: int, tzinfo: TzInfo
) -> tuple[datetime, datetime, str]:
    if quarter == 1:
        start = datetime(fy_year, 2, 1, tzinfo=tzinfo)
        end = datetime(fy_year, 4, 30, 23, 59, 59, 999999, tzinfo=tzinfo)
        label = f"Q1 FY{fy_year}"
    elif quarter == 2:
        start = datetime(fy_year, 5, 1, tzinfo=tzinfo)
        end = datetime(fy_year, 7, 31, 23, 59, 59, 999999, tzinfo=tzinfo)
        label = f"Q2 FY{fy_year}"
    elif quarter == 3:
        start = datetime(fy_year, 8, 1, tzinfo=tzinfo)
        end = datetime(fy_year, 10, 31, 23, 59, 59, 999999, tzinfo=tzinfo)
        label = f"Q3 FY{fy_year}"
    else:
        start = datetime(fy_year, 11, 1, tzinfo=tzinfo)
        end = datetime(fy_year + 1, 1, 31, 23, 59, 59, 999999, tzinfo=tzinfo)
        label = f"Q4 FY{fy_year}"
    return start, end, label


def _get_quarter_periods(now: datetime) -> list[dict]:
    periods = []
    fy_year, quarter = _current_fiscal_quarter(now)
    for _ in range(_HISTORY_QUARTERS):
        start, end, label = _get_fiscal_quarter_bounds(fy_year, quarter, now.tzinfo)  # type: ignore[arg-type]
        periods.append({"label": label, "start": start, "end": end})
        fy_year, quarter = _prev_fiscal_quarter(fy_year, quarter)
    return periods


def _current_fiscal_year(now: datetime) -> int:
    return now.year if now.month >= 2 else now.year - 1


def _get_year_periods(now: datetime) -> list[dict]:
    periods = []
    fy_year = _current_fiscal_year(now)
    for _ in range(_HISTORY_YEARS):
        start = datetime(fy_year, 2, 1, tzinfo=now.tzinfo)
        end = datetime(fy_year + 1, 1, 31, 23, 59, 59, 999999, tzinfo=now.tzinfo)
        label = f"FY{fy_year}"
        periods.append({"label": label, "start": start, "end": end})
        fy_year -= 1
    return periods


def _compute_regions(
    tags: QuerySet[Tag], period_start: datetime, period_end: datetime, now: datetime
) -> list[dict]:
    effective_end = min(period_end, now)
    total_period_seconds = (period_end - period_start).total_seconds()
    regions = []
    for tag in tags:
        incidents_qs = Incident.objects.filter(
            affected_region_tags=tag,
            created_at__gte=period_start,
            created_at__lte=effective_end,
            total_downtime__isnull=False,
            service_tier="T0",
        ).order_by("-created_at")
        # total_downtime is stored in minutes; convert to seconds for availability calculation
        total_downtime_minutes = (
            incidents_qs.aggregate(total=Sum("total_downtime"))["total"] or 0
        )
        total_downtime_seconds = total_downtime_minutes * 60
        availability_pct = max(
            0.0,
            (total_period_seconds - total_downtime_seconds)
            / total_period_seconds
            * 100,
        )
        incident_list = [
            {
                "id": inc.id,
                "title": inc.title,
                "created_at": inc.created_at.isoformat(),
                "total_downtime_minutes": inc.total_downtime,
                "total_downtime_display": inc.total_downtime_display,
            }
            for inc in incidents_qs
        ]
        regions.append(
            {
                "name": tag.name,
                "total_downtime_minutes": total_downtime_minutes,
                "total_downtime_display": _format_downtime(total_downtime_minutes),
                "availability_percentage": round(availability_pct, 6),
                "incident_count": len(incident_list),
                "incidents": incident_list,
            }
        )
    return regions


class AvailabilityView(APIView):
    """GET /api/ui/availability/ — Returns availability by region for month/quarter/year."""

    def get(self, request: Request) -> Response:
        now = timezone.now()
        tags = Tag.objects.filter(type=TagType.AFFECTED_REGION).order_by("name")

        def build_periods(raw_periods: list[dict]) -> list[dict]:
            return [
                {
                    "label": p["label"],
                    "start": p["start"].isoformat(),
                    "end": p["end"].isoformat(),
                    "regions": _compute_regions(tags, p["start"], p["end"], now),
                }
                for p in raw_periods
            ]

        return Response(
            {
                "months": build_periods(_get_month_periods(now)),
                "quarters": build_periods(_get_quarter_periods(now)),
                "years": build_periods(_get_year_periods(now)),
            }
        )
