from django.urls import path

from .views import (
    IncidentListCreateAPIView,
    IncidentRetrieveUpdateAPIView,
    incident_detail_ui,
    incident_list_ui,
)

urlpatterns = [
    # UI endpoints (for frontend)
    path("ui/incidents/", incident_list_ui, name="incident-list-ui"),
    path(
        "ui/incidents/<str:incident_id>/",
        incident_detail_ui,
        name="incident-detail-ui",
    ),
    # Programmatic API endpoints
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
]
