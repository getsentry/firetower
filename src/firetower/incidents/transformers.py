"""
Transformers for converting data between different formats.

This module contains functions to transform data from external sources
(like Jira) into the format expected by the frontend API.
"""


def transform_jira_incident_for_list(jira_incident):
    """Transform a Jira incident to the format expected by the frontend list."""
    return {
        "id": jira_incident['id'],
        "title": jira_incident['title'],
        "description": jira_incident['description'],
        "status": jira_incident['status'],  # Jira already has the correct status values
        "severity": jira_incident.get('severity'),  # Jira already has severity field
        "created_at": jira_incident['created_at'],
        "is_private": False,  # TODO: Determine privacy from Jira fields
    }


def transform_jira_incident_for_detail(jira_incident):
    """Transform a Jira incident to the detailed format expected by the frontend."""
    return {
        "id": jira_incident['id'],
        "title": jira_incident['title'],
        "description": jira_incident['description'],
        "impact": "",  # TODO: Map to proper impact field
        "status": jira_incident['status'],  # Jira already has the correct status values
        "severity": jira_incident.get('severity'),  # Jira already has severity field
        "created_at": jira_incident['created_at'],
        "updated_at": jira_incident['updated_at'],
        "is_private": False,  # TODO: Determine privacy from Jira fields
        "affected_areas": [],  # TODO: Extract from Jira custom fields
        "root_causes": [],  # TODO: Extract from Jira custom fields
        "participants": extract_participants(jira_incident),
        "external_links": {
            "slack": None,  # TODO: Extract from Jira fields
            "jira": f"https://getsentry.atlassian.net/browse/{jira_incident['id']}",
            "datadog": None,  # TODO: Extract from Jira fields
            "pagerduty": None,  # TODO: Extract from Jira fields  
            "statuspage": None,  # TODO: Extract from Jira fields
        },
    }


def extract_participants(jira_incident):
    """Extract participants from Jira incident data."""
    participants = []
    
    # Add assignee as Captain if present (Jira assignee = Captain)
    if jira_incident.get('assignee'):
        participants.append({
            "name": jira_incident['assignee'],
            "slack": jira_incident['assignee'].lower().replace(' ', '.'),  # TODO: Proper slack mapping
            "avatar_url": f"https://via.placeholder.com/32x32?text={jira_incident['assignee'][0]}",  # TODO: Real avatars
            "role": "Captain",
        })
    
    # Add reporter if present and different from assignee
    if jira_incident.get('reporter') and jira_incident['reporter'] != jira_incident.get('assignee'):
        participants.append({
            "name": jira_incident['reporter'],
            "slack": jira_incident['reporter'].lower().replace(' ', '.'),  # TODO: Proper slack mapping  
            "avatar_url": f"https://via.placeholder.com/32x32?text={jira_incident['reporter'][0]}",  # TODO: Real avatars
            "role": "Reporter",
        })
    
    return participants