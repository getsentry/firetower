import logging
import re
from collections import defaultdict
from dataclasses import asdict

from django.conf import settings
from django.db.models import Count, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import (
    filter_by_captain,
    filter_by_date_range,
    filter_by_reporter,
    filter_by_service_tier,
    filter_by_severity,
    filter_by_status,
    filter_by_tags,
)
from .models import (
    INCIDENT_ID_START,
    Incident,
    IncidentOrRedirect,
    Tag,
    TagType,
    filter_visible_to_user,
)
from .permissions import IncidentPermission
from .reporting_utils import (
    build_incidents_by_tag,
    compute_regions,
    get_month_periods,
    get_quarter_periods,
    get_year_periods,
)
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


class AvailabilityView(APIView):
    """GET /api/ui/availability/ — Returns availability by region for month/quarter/year."""

    def get(self, request: Request) -> Response:
        now = timezone.now()
        tags = list(Tag.objects.filter(type=TagType.AFFECTED_REGION).order_by("name"))

        month_periods = get_month_periods(now)
        quarter_periods = get_quarter_periods(now)
        year_periods = get_year_periods(now)
        all_periods = month_periods + quarter_periods + year_periods

        # Fetch all relevant incidents in 2 queries (fetch + prefetch),
        # then filter per period×tag in Python to avoid 46×N DB queries.
        incidents_by_tag: dict[int, list[Incident]] = defaultdict(list)
        if all_periods and tags:
            earliest_start = min(p["start"] for p in all_periods)
            incidents = list(
                filter_visible_to_user(
                    Incident.objects.filter(
                        created_at__gte=earliest_start,
                        created_at__lte=now,
                        total_downtime__isnull=False,
                        service_tier="T0",
                    ),
                    request.user,
                ).prefetch_related("affected_region_tags")
            )
            incidents_by_tag = build_incidents_by_tag(incidents)

        def build_periods(raw_periods: list[dict]) -> list[dict]:
            return [
                {
                    "label": p["label"],
                    "start": p["start"].isoformat(),
                    "end": p["end"].isoformat(),
                    "regions": compute_regions(
                        tags, p["start"], p["end"], now, incidents_by_tag
                    ),
                }
                for p in raw_periods
            ]

        return Response(
            {
                "months": build_periods(month_periods),
                "quarters": build_periods(quarter_periods),
                "years": build_periods(year_periods),
            }
        )
