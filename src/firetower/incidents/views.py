import logging
import re
from dataclasses import asdict

from django.conf import settings
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Incident, filter_visible_to_user
from .permissions import IncidentPermission
from .serializers import (
    IncidentDetailUISerializer,
    IncidentListUISerializer,
    IncidentReadSerializer,
    IncidentWriteSerializer,
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
    - Privacy: users only see public incidents + their own private incidents

    Authentication enforced via DEFAULT_PERMISSION_CLASSES in settings.
    """

    serializer_class = IncidentListUISerializer

    def get_queryset(self) -> QuerySet[Incident]:
        """Filter incidents by visibility and status"""
        queryset = Incident.objects.all()
        queryset = filter_visible_to_user(queryset, self.request.user)

        # Filter by status (defaults to Active and Mitigated if not specified)
        status_filters = self.request.GET.getlist("status")
        if not status_filters:
            status_filters = ["Active", "Mitigated"]
        queryset = queryset.filter(status__in=status_filters)

        return queryset


class IncidentDetailUIView(generics.RetrieveAPIView):
    """
    Get specific incident details from database.

    Accepts incident_id in format: INC-2000
    Returns 404 if incident not found or user doesn't have access.
    Uses prefetch_related for optimized queries.

    Authentication enforced via DEFAULT_PERMISSION_CLASSES in settings.
    """

    serializer_class = IncidentDetailUISerializer
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[Incident]:
        """Get base queryset with optimized prefetching"""
        return Incident.objects.prefetch_related(
            "captain__userprofile",
            "reporter__userprofile",
            "participants__userprofile",
            "affected_area_tags",
            "root_cause_tags",
            "external_links",
        )

    def get_object(self) -> Incident:
        """
        Parse INC-2000 format and filter by visibility.

        Returns incident if found and user has access, otherwise 404.
        """
        incident_id = self.kwargs["incident_id"]
        project_key = settings.PROJECT_KEY

        # Extract numeric ID from incident number (INC-2000 -> 2000)
        incident_pattern = rf"^{re.escape(project_key)}-(\d+)$"
        match = re.match(incident_pattern, incident_id)

        if not match:
            raise ValidationError(
                f"Invalid incident ID format. Expected format: {project_key}-<number> (e.g., {project_key}-123)"
            )

        # Get incident by numeric ID
        numeric_id = int(match.group(1))
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

        return incident


# View aliases for cleaner URL imports
incident_list_ui = IncidentListUIView.as_view()
incident_detail_ui = IncidentDetailUIView.as_view()


@method_decorator(csrf_exempt, name="dispatch")
class IncidentListCreateAPIView(generics.ListCreateAPIView):
    """
    Service API for listing and creating incidents.

    GET: List all incidents visible to the user (no search/filtering for now)
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
        """Filter incidents by visibility only"""
        queryset = Incident.objects.all()
        queryset = filter_visible_to_user(queryset, self.request.user)
        return queryset


@method_decorator(csrf_exempt, name="dispatch")
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
            "affected_area_tags",
            "root_cause_tags",
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

        # Extract numeric ID from incident number (INC-2000 -> 2000)
        incident_pattern = rf"^{re.escape(project_key)}-(\d+)$"
        match = re.match(incident_pattern, incident_id)

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


@method_decorator(csrf_exempt, name="dispatch")
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

        incident_pattern = rf"^{re.escape(project_key)}-(\d+)$"
        match = re.match(incident_pattern, incident_id)

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
