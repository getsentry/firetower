import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    Tag,
    TagType,
)


@pytest.mark.django_db
class TestIncidentViews:
    def setup_method(self):
        """Set up test client and common test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            password="testpass123",
        )

    def test_list_incidents(self):
        """Test GET /api/ui/incidents/ returns list of incidents"""
        # Create test incidents
        Incident.objects.create(
            title="Test Incident 1",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.create(
            title="Test Incident 2",
            status=IncidentStatus.MITIGATED,
            severity=IncidentSeverity.P2,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/")

        assert response.status_code == 200
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2

        # Check list serializer format
        incident = response.data["results"][0]
        assert "id" in incident  # INC-XXXX format
        assert "title" in incident
        assert "status" in incident
        assert "severity" in incident

    def test_list_incidents_respects_privacy(self):
        """Test private incidents are filtered correctly"""
        # Create public and private incidents
        Incident.objects.create(
            title="Public Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=False,
        )
        Incident.objects.create(
            title="Private Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
            captain=self.user,
        )
        Incident.objects.create(
            title="Someone Else's Private",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/")

        assert response.status_code == 200
        assert response.data["count"] == 2  # Public + user's private
        assert len(response.data["results"]) == 2

        titles = [inc["title"] for inc in response.data["results"]]
        assert "Public Incident" in titles
        assert "Private Incident" in titles
        assert "Someone Else's Private" not in titles

    def test_list_incidents_filter_by_status(self):
        """Test filtering incidents by status"""
        Incident.objects.create(
            title="Active Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.create(
            title="Mitigated Incident",
            status=IncidentStatus.MITIGATED,
            severity=IncidentSeverity.P2,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/?status=Active")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["title"] == "Active Incident"

    def test_list_incidents_filter_by_multiple_statuses(self):
        """Test filtering by multiple statuses"""
        Incident.objects.create(
            title="Active",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.create(
            title="Mitigated",
            status=IncidentStatus.MITIGATED,
            severity=IncidentSeverity.P2,
        )
        Incident.objects.create(
            title="Done",
            status=IncidentStatus.DONE,
            severity=IncidentSeverity.P3,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/?status=Active&status=Mitigated")

        assert response.status_code == 200
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2

    def test_retrieve_incident(self):
        """Test GET /api/ui/incidents/INC-2000/ returns full incident details"""
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Jane",
            last_name="Captain",
        )
        incident = Incident.objects.create(
            title="Test Incident",
            description="Test description",
            impact="Test impact",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=captain,
        )

        # Add tags
        area_tag = Tag.objects.create(name="API", type=TagType.AFFECTED_AREA)
        incident.affected_area_tags.add(area_tag)

        # Add external link
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/test",
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/ui/incidents/{incident.incident_number}/")

        assert response.status_code == 200

        # Check detail serializer format
        data = response.data
        assert data["id"] == incident.incident_number
        assert data["title"] == "Test Incident"

        # Captain should be in participants list
        assert len(data["participants"]) == 1
        assert data["participants"][0]["name"] == "Jane Captain"
        assert data["participants"][0]["role"] == "Captain"

        # Detail view includes full data
        assert "affected_areas" in data
        assert "API" in data["affected_areas"]
        assert "external_links" in data
        assert data["external_links"]["slack"] == "https://slack.com/test"

    def test_retrieve_incident_respects_privacy(self):
        """Test private incident detail respects permissions"""
        other_user = User.objects.create_user(
            username="other@example.com",
            password="testpass123",
        )
        incident = Incident.objects.create(
            title="Private Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
            captain=other_user,
        )

        # User without permission tries to access
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/incidents/{incident.incident_number}/")

        assert response.status_code == 404

    def test_retrieve_incident_invalid_format(self):
        """Test invalid incident ID format returns 400"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/INVALID-123/")

        assert response.status_code == 400

    def test_unauthenticated_detail_request(self):
        """Test unauthenticated detail request returns 403 (DRF permission denied)"""
        incident = Incident.objects.create(
            title="Test",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        # Don't authenticate
        response = self.client.get(f"/api/ui/incidents/{incident.incident_number}/")

        # Behind IAP, unauthenticated requests should be blocked
        # DRF permissions return 403 Forbidden
        assert response.status_code == 403

    def test_retrieve_incident_not_found(self):
        """Test non-existent incident returns 404"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/INC-99999/")

        assert response.status_code == 404

    def test_superuser_sees_all_private_incidents(self):
        """Test superuser can see all incidents including private ones"""
        superuser = User.objects.create_superuser(
            username="admin@example.com",
            email="admin@example.com",
            password="testpass123",
        )

        Incident.objects.create(
            title="Public",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=False,
        )
        Incident.objects.create(
            title="Private",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
        )

        self.client.force_authenticate(user=superuser)
        response = self.client.get("/api/ui/incidents/")

        assert response.status_code == 200
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2

    def test_unauthenticated_request(self):
        """Test unauthenticated requests return 403 (DRF permission denied)"""
        Incident.objects.create(
            title="Test",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        # Don't authenticate
        response = self.client.get("/api/ui/incidents/")

        # Behind IAP, unauthenticated requests should be blocked
        # DRF permissions return 403 Forbidden
        assert response.status_code == 403
