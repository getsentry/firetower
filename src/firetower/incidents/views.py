from rest_framework.decorators import api_view
from rest_framework.response import Response


DUMMY_INCIDENTS = [
    {
        "id": "INC-1247",
        "title": "Database Connection Pool Exhausted",
        "description": "Users experiencing 500 errors when trying to access their dashboard. Database connection pool appears to be exhausted, causing new requests to timeout.",
        "status": "Actions Pending",
        "severity": "P1",
        "created_at": "2024-08-27T14:14:00Z",
        "is_private": False,
    },
    {
        "id": "INC-1246",
        "title": "SSL Certificate Renewal Failed",
        "description": "Automated SSL certificate renewal process failed for api.example.com. Manual intervention required to restore HTTPS access.",
        "status": "Mitigated",
        "severity": "P2",
        "created_at": "2024-08-27T11:32:00Z",
        "is_private": False,
    },
    {
        "id": "INC-1245",
        "title": "Redis Cache Performance Degradation",
        "description": "Cache hit rates dropped significantly causing increased database load and slower response times.",
        "status": "Active",
        "severity": "P1",
        "created_at": "2024-08-28T09:15:00Z",
        "is_private": True,
    },
]

DUMMY_INCIDENT_DETAIL = {
    "id": "INC-1247",
    "title": "Database Connection Pool Exhausted",
    "description": "Users experiencing 500 errors when trying to access their dashboard. Database connection pool appears to be exhausted, causing new requests to timeout. Investigation shows unusual spike in traffic from API endpoint.",
    "impact": "500 errors affecting 15% of users attempting to access dashboard. Authentication flow completely blocked for new sign-ups.",
    "status": "Actions Pending",
    "severity": "P1",
    "created_at": "2024-08-27T14:14:00Z",
    "updated_at": "2024-08-27T16:32:00Z",
    "is_private": True,
    "affected_areas": ["API", "Database", "User Dashboard", "Authentication"],
    "root_causes": ["Resource Exhaustion", "Traffic Spike"],
    "participants": [
        {
            "name": "John Smith",
            "slack": "john.smith",
            "avatar_url": "https://ca.slack-edge.com/T025K2Q1T-U123456-abc123def456/192",
            "role": "Captain",
        },
        {
            "name": "Jane Doe",
            "slack": "jane.doe",
            "avatar_url": "https://ca.slack-edge.com/T025K2Q1T-U234567-def456ghi789/192",
            "role": "Reporter",
        },
        {
            "name": "Alice Brown",
            "slack": "alice.brown",
            "avatar_url": "https://ca.slack-edge.com/T025K2Q1T-U345678-ghi789jkl012/192",
            "role": None,
        },
    ],
    "external_links": {
        "slack": "https://sentry.slack.com/channels/inc-1247",
        "jira": "https://sentry.atlassian.net/browse/INC-1247",
        "datadog": "https://app.datadoghq.com/dashboard/abc-123",
        "pagerduty": "https://sentry.pagerduty.com/incidents/P1234",
        "statuspage": "https://status.sentry.io/incidents/xyz-789",
    },
}


@api_view(["GET"])
def incident_list_ui(request):
    """List all incidents"""
    return Response(DUMMY_INCIDENTS)


@api_view(["GET"])
def incident_detail_ui(request, incident_id):
    """Get specific incident details"""
    # For now, just return the same detail data regardless of ID
    detail = DUMMY_INCIDENT_DETAIL.copy()
    detail["id"] = incident_id
    detail["title"] = f"Incident {incident_id}"
    return Response(detail)
