from django.urls import path
from .views import incident_list_ui, incident_detail_ui

urlpatterns = [
    path("api/ui/incidents/", incident_list_ui, name="incident-list-ui"),
    path(
        "api/ui/incidents/<str:incident_id>/",
        incident_detail_ui,
        name="incident-detail-ui",
    ),
]
