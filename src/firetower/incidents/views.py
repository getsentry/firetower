import re

from django.conf import settings
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import ValidationError

from .models import Incident, filter_visible_to_user
from .serializers import IncidentDetailUISerializer, IncidentListUISerializer


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

        # Returns 404 if not found OR if user doesn't have access
        return get_object_or_404(queryset, id=numeric_id)


# Backwards-compatible function-based view aliases (for gradual migration)
incident_list_ui = IncidentListUIView.as_view()
incident_detail_ui = IncidentDetailUIView.as_view()
