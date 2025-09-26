import re

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from firetower.integrations.services.jira import JiraService

from .transformers import (
    transform_jira_incident_for_detail,
    transform_jira_incident_for_list,
)


@api_view(["GET"])
def incident_list_ui(request):
    """List all incidents from Jira"""
    try:
        jira_service = JiraService()
        status_filter = request.GET.get("status")
        jira_incidents = jira_service.get_incidents(
            status=status_filter, max_results=50
        )
        incidents = [
            transform_jira_incident_for_list(incident) for incident in jira_incidents
        ]

        return Response(incidents)

    except Exception as e:
        print(f"Error fetching incidents: {e}")
        return Response(
            {"error": "Failed to fetch incidents"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
def incident_detail_ui(request, incident_id):
    """Get specific incident details from Jira"""
    project_key = settings.JIRA["PROJECT_KEY"]
    incident_pattern = rf"^{re.escape(project_key)}-\d+$"

    if not re.match(incident_pattern, incident_id):
        return Response(
            {
                "error": f"Invalid incident ID format. Expected format: {project_key}-<number> (e.g., {project_key}-123)"
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        jira_service = JiraService()
        jira_incident = jira_service.get_incident(incident_id)

        if not jira_incident:
            return Response(
                {"error": f"Incident {incident_id} not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        incident_detail = transform_jira_incident_for_detail(jira_incident)

        return Response(incident_detail)

    except Exception as e:
        print(f"Error fetching incident {incident_id}: {e}")
        return Response(
            {"error": f"Failed to fetch incident {incident_id}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
