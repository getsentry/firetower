import re
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from firetower.integrations.services.jira import JiraService
from .transformers import (
    transform_jira_incident_for_list,
    transform_jira_incident_for_detail,
)


@api_view(["GET"])
def incident_list_ui(request):
    """List all incidents from Jira"""
    try:
        # Initialize Jira service
        jira_service = JiraService()
        
        # Get status filter from query params
        status_filter = request.GET.get('status')
        
        # Fetch incidents from Jira
        jira_incidents = jira_service.get_incidents(status=status_filter, max_results=50)
        
        # Transform to frontend format
        incidents = [transform_jira_incident_for_list(incident) for incident in jira_incidents]
        
        return Response(incidents)
        
    except Exception as e:
        print(f"Error fetching incidents: {e}")
        return Response(
            {"error": "Failed to fetch incidents"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET"])
def incident_detail_ui(request, incident_id):
    """Get specific incident details from Jira"""
    # Validate incident ID format before hitting Jira
    project_key = settings.JIRA['PROJECT_KEY']
    incident_pattern = rf"^{re.escape(project_key)}-\d+$"
    
    if not re.match(incident_pattern, incident_id):
        return Response(
            {"error": f"Invalid incident ID format. Expected format: {project_key}-<number> (e.g., {project_key}-123)"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    try:
        # Initialize Jira service
        jira_service = JiraService()
        
        # Fetch incident from Jira
        jira_incident = jira_service.get_incident(incident_id)

        print(jira_incident)
        
        if not jira_incident:
            return Response(
                {"error": f"Incident {incident_id} not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Transform to frontend format
        incident_detail = transform_jira_incident_for_detail(jira_incident)
        
        return Response(incident_detail)
        
    except Exception as e:
        print(f"Error fetching incident {incident_id}: {e}")
        return Response(
            {"error": f"Failed to fetch incident {incident_id}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
