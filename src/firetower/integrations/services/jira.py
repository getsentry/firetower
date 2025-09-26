"""
Jira integration service for fetching incident data.

This service provides a simple interface to interact with Jira's REST API
and transform Jira issues into our incident data format.
"""

import re

from django.conf import settings
from jira import JIRA


class JiraService:
    """
    Service class for interacting with Jira API.

    Provides methods to fetch incident data from Jira and transform it
    into a format suitable for the Firetower application.
    """

    def __init__(self):
        """Initialize the Jira service."""
        # Get Jira configuration from Django settings
        jira_config = settings.JIRA

        # Validate required settings
        if not jira_config["ACCOUNT"] or not jira_config["API_KEY"]:
            raise ValueError("Jira credentials not configured in settings.JIRA")

        # Store config for later use
        self.domain = jira_config["DOMAIN"]
        self.project_key = jira_config["PROJECT_KEY"]
        self.severity_field_id = jira_config["SEVERITY_FIELD"]

        # Initialize Jira client with basic auth
        self.client = JIRA(
            self.domain, basic_auth=(jira_config["ACCOUNT"], jira_config["API_KEY"])
        )

    def _extract_severity(self, issue):
        """Extract severity from Jira custom field."""
        severity_field = getattr(issue.fields, self.severity_field_id, None)
        return getattr(severity_field, "value", None) if severity_field else None

    def get_incident(self, incident_key: str):
        """
        Fetch a single incident by its Jira key.

        Args:
            incident_key (str): Jira issue key (e.g., 'INC-1247')

        Returns:
            dict: Incident data or None if not found
        """
        issue = self.client.issue(incident_key)

        return {
            "id": issue.key,
            "title": issue.fields.summary,
            "description": getattr(issue.fields, "description", "") or "",
            "status": issue.fields.status.name,
            "severity": self._extract_severity(issue),
            "assignee": issue.fields.assignee.displayName
            if issue.fields.assignee
            else None,
            "reporter": issue.fields.reporter.displayName
            if issue.fields.reporter
            else None,
            "created_at": issue.fields.created,
            "updated_at": issue.fields.updated,
        }

    def get_incidents(self, status: str = "", max_results=50):
        """
        Fetch a list of incidents from the Jira project.

        Args:
            status (str, optional): Filter by status (e.g., 'Active', 'Postmortem', 'Actions Pending')
            max_results (int): Maximum number of incidents to return (default: 50)

        Returns:
            list: List of incident data dictionaries
        """
        jql_parts = [f'project = "{self.project_key}"']

        if status:
            if not re.match(r"^[A-Za-z\s]+$", status):
                raise ValueError(
                    f"Invalid status format: {status}. Only alphabetical characters and spaces allowed."
                )
            jql_parts.append(f'status = "{status}"')

        jql_query = " AND ".join(jql_parts)
        jql_query += " ORDER BY created DESC"

        issues = self.client.search_issues(
            jql_query, maxResults=max_results, expand="changelog"
        )

        incidents = []
        for issue in issues:
            incident_data = {
                "id": issue.key,
                "title": issue.fields.summary,
                "description": getattr(issue.fields, "description", "") or "",
                "status": issue.fields.status.name,
                "severity": self._extract_severity(issue),
                "assignee": issue.fields.assignee.displayName
                if issue.fields.assignee
                else None,
                "reporter": issue.fields.reporter.displayName
                if issue.fields.reporter
                else None,
                "created_at": issue.fields.created,
                "updated_at": issue.fields.updated,
            }
            incidents.append(incident_data)

        return incidents
