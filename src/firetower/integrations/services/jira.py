"""
Jira integration service for fetching incident data.

This service provides a simple interface to interact with Jira's REST API
and transform Jira issues into our incident data format.
"""
from django.conf import settings
from jira import JIRA
from jira.exceptions import JIRAError

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
        if not jira_config['ACCOUNT'] or not jira_config['API_KEY']:
            raise ValueError("Jira credentials not configured in settings.JIRA")
        
        # Store config for later use
        self.domain = jira_config['DOMAIN']
        self.project_key = jira_config['PROJECT_KEY']
        
        # Initialize Jira client with basic auth
        self.client = JIRA(
            self.domain,
            basic_auth=(jira_config['ACCOUNT'], jira_config['API_KEY'])
        )
    
    def get_incident(self, incident_key: str):
        """
        Fetch a single incident by its Jira key.
        
        Args:
            incident_key (str): Jira issue key (e.g., 'INC-1247')
            
        Returns:
            dict: Incident data or None if not found
        """
        try:
            # Fetch the issue from Jira
            issue = self.client.issue(incident_key)
            
            # Return basic incident data (we'll expand this later)
            return {
                'id': issue.key,
                'title': issue.fields.summary,
                'description': getattr(issue.fields, 'description', '') or '',
                'status': issue.fields.status.name,
                'created_at': issue.fields.created,
                'updated_at': issue.fields.updated,
            }
            
        except JIRAError as e:
            # Log the error in a real app, for now just return None
            return None
