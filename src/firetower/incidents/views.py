import logging
import re
from dataclasses import asdict
from datetime import datetime

from django.conf import settings
from django.db.models import Count, QuerySet
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from .models import (
    INCIDENT_ID_START,
    Incident,
    IncidentOrRedirect,
    IncidentSeverity,
    IncidentStatus,
    ServiceTier,
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
        queryset = Incident.objects.all()
        queryset = filter_visible_to_user(queryset, self.request.user)
        queryset = filter_by_status(
            queryset, self.request, default=["Active", "Mitigated"]
        )
        queryset = filter_by_severity(queryset, self.request)
        queryset = filter_by_service_tier(queryset, self.request)
        queryset = filter_by_date_range(queryset, self.request)
        queryset = filter_by_tags(queryset, self.request)
        queryset = filter_by_captain(queryset, self.request)
        queryset = filter_by_reporter(queryset, self.request)
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
        queryset = Incident.objects.all()
        queryset = filter_visible_to_user(queryset, self.request.user)
        queryset = filter_by_status(queryset, self.request)
        queryset = filter_by_severity(queryset, self.request)
        queryset = filter_by_service_tier(queryset, self.request)
        queryset = filter_by_date_range(queryset, self.request)
        queryset = filter_by_tags(queryset, self.request)
        queryset = filter_by_captain(queryset, self.request)
        queryset = filter_by_reporter(queryset, self.request)
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
