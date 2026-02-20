from django.urls import path

from .views import (
    AvailabilityView,
    IncidentListCreateAPIView,
    IncidentRetrieveUpdateAPIView,
    TagListCreateAPIView,
    incident_detail_ui,
    incident_list_ui,
    sync_incident_participants,
)

urlpatterns = [
    # UI endpoints (for frontend)
    path("ui/incidents/", incident_list_ui, name="incident-list-ui"),
    path(
        "ui/incidents/<str:incident_id>/",
        incident_detail_ui,
        name="incident-detail-ui",
    ),
    path("ui/availability/", AvailabilityView.as_view(), name="ui-availability"),
    # Service API endpoints
    path(
        "incidents/",
        IncidentListCreateAPIView.as_view(),
        name="incident-list-create",
    ),
    path(
        "incidents/<str:incident_id>/",
        IncidentRetrieveUpdateAPIView.as_view(),
        name="incident-retrieve-update",
    ),
    path(
        "incidents/<str:incident_id>/sync-participants/",
        sync_incident_participants,
        name="sync-incident-participants",
    ),
    path(
        "tags/",
        TagListCreateAPIView.as_view(),
        name="tag-list-create",
    ),
]
