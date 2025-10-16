"""
Transformers for converting data between different formats.

This module contains functions to transform data from external sources
(like Jira) into the format expected by the frontend API.
"""

from firetower.integrations.services.slack import SlackService


def transform_jira_incident_for_list(jira_incident):
    """Transform a Jira incident to the format expected by the frontend list."""
    return {
        "id": jira_incident["id"],
        "title": jira_incident["title"],
        "description": jira_incident["description"],
        "status": jira_incident["status"],
        "severity": jira_incident.get("severity"),
        "created_at": jira_incident["created_at"],
        "is_private": False,
    }


def transform_jira_incident_for_detail(jira_incident):
    """Transform a Jira incident to the detailed format expected by the frontend."""
    slack_service = SlackService()
    slack_url = slack_service.get_channel_url_by_name(jira_incident["id"].lower())
    return {
        "id": jira_incident["id"],
        "title": jira_incident["title"],
        "description": jira_incident["description"],
        "impact": "",
        "status": jira_incident["status"],
        "severity": jira_incident.get("severity"),
        "created_at": jira_incident["created_at"],
        "updated_at": jira_incident["updated_at"],
        "is_private": False,
        "affected_areas": [],
        "root_causes": [],
        "participants": extract_participants(jira_incident),
        "external_links": {
            "slack": slack_url,
            "jira": f"https://getsentry.atlassian.net/browse/{jira_incident['id']}",
            "datadog": None,
            "pagerduty": None,
            "statuspage": None,
        },
    }


def extract_participants(jira_incident):
    """Extract participants from both Jira and Slack."""
    participants = []
    incident_id = jira_incident["id"].lower()

    slack_service = SlackService()
    slack_participants = slack_service.get_channel_participants(incident_id)

    if slack_participants:
        participants_by_email = {
            p.get("email", "").lower(): p for p in slack_participants if p.get("email")
        }

        if jira_incident.get("assignee_email"):
            assignee_email = jira_incident["assignee_email"].lower()
            participant = participants_by_email.get(assignee_email)
            if participant:
                participant["role"] = "Captain"
            else:
                new_participant = {
                    "name": jira_incident.get("assignee", "Unknown"),
                    "email": jira_incident["assignee_email"],
                    "avatar_url": None,
                    "role": "Captain",
                }
                participants.append(new_participant)

        if jira_incident.get("reporter_email") and jira_incident.get(
            "reporter_email"
        ) != jira_incident.get("assignee_email"):
            reporter_email = jira_incident["reporter_email"].lower()
            participant = participants_by_email.get(reporter_email)
            if participant:
                participant["role"] = "Reporter"
            else:
                new_participant = {
                    "name": jira_incident.get("reporter", "Unknown"),
                    "email": jira_incident["reporter_email"],
                    "avatar_url": None,
                    "role": "Reporter",
                }
                participants.append(new_participant)

        participants.extend(slack_participants)

    else:
        if jira_incident.get("assignee"):
            participants.append(
                {
                    "name": jira_incident["assignee"],
                    "email": jira_incident.get("assignee_email"),
                    "avatar_url": None,
                    "role": "Captain",
                }
            )

        if jira_incident.get("reporter") and jira_incident[
            "reporter"
        ] != jira_incident.get("assignee"):
            participants.append(
                {
                    "name": jira_incident["reporter"],
                    "email": jira_incident.get("reporter_email"),
                    "avatar_url": None,
                    "role": "Reporter",
                }
            )

    return participants
