import time
from datetime import datetime
from unittest.mock import patch

import pytest
from django.conf import settings
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
from firetower.incidents.services import ParticipantsSyncStats


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

    def test_list_incidents_defaults_to_active_and_mitigated(self):
        """Test that no status filter defaults to Active and Mitigated"""
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
        Incident.objects.create(
            title="Done Incident",
            status=IncidentStatus.DONE,
            severity=IncidentSeverity.P3,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/")

        assert response.status_code == 200
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2
        titles = [inc["title"] for inc in response.data["results"]]
        assert "Active Incident" in titles
        assert "Mitigated Incident" in titles
        assert "Done Incident" not in titles

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
        assert "affected_area_tags" in data
        assert "API" in data["affected_area_tags"]
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

    def test_retrieve_incident_not_found(self):
        """Test non-existent incident returns 404"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/ui/incidents/{settings.PROJECT_KEY}-99999/")

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

    def test_retrieve_incident_syncs_participants(self):
        """Test that retrieving incident details syncs participants from Slack"""
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        with patch(
            "firetower.incidents.views.sync_incident_participants_from_slack"
        ) as mock_sync:
            self.client.force_authenticate(user=self.user)
            response = self.client.get(f"/api/ui/incidents/{incident.incident_number}/")

            assert response.status_code == 200
            mock_sync.assert_called_once_with(incident)

    def test_retrieve_incident_does_not_fail_on_sync_error(self):
        """Test that incident retrieval succeeds even if participant sync fails"""
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        with patch(
            "firetower.incidents.views.sync_incident_participants_from_slack"
        ) as mock_sync:
            mock_sync.side_effect = Exception("Slack API error")

            self.client.force_authenticate(user=self.user)
            response = self.client.get(f"/api/ui/incidents/{incident.incident_number}/")

            assert response.status_code == 200
            assert response.data["id"] == incident.incident_number

    def test_sync_participants_endpoint(self):
        """Test POST /api/incidents/{id}/sync-participants/ forces sync"""
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        with patch(
            "firetower.incidents.views.sync_incident_participants_from_slack"
        ) as mock_sync:
            mock_sync.return_value = ParticipantsSyncStats(
                added=3,
                already_existed=5,
            )

            self.client.force_authenticate(user=self.user)
            response = self.client.post(
                f"/api/incidents/{incident.incident_number}/sync-participants/"
            )

            assert response.status_code == 200
            assert response.data["success"] is True
            assert response.data["stats"]["added"] == 3
            assert response.data["stats"]["already_existed"] == 5
            mock_sync.assert_called_once_with(incident, force=True)

    def test_sync_participants_endpoint_handles_errors(self):
        """Test sync endpoint returns 500 on error"""
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        with patch(
            "firetower.incidents.views.sync_incident_participants_from_slack"
        ) as mock_sync:
            mock_sync.side_effect = Exception("Slack API error")

            self.client.force_authenticate(user=self.user)
            response = self.client.post(
                f"/api/incidents/{incident.incident_number}/sync-participants/"
            )

            assert response.status_code == 500
            assert response.data["success"] is False
            assert response.data["error"] == "Failed to sync participants from Slack"
            assert len(response.data["stats"]["errors"]) > 0
            assert (
                response.data["stats"]["errors"][0]
                == "Failed to sync participants from Slack"
            )

    def test_sync_participants_endpoint_respects_privacy(self):
        """Test sync endpoint returns 404 for private incidents user can't access"""
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

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/incidents/{incident.incident_number}/sync-participants/"
        )

        assert response.status_code == 404

    def test_sync_participants_endpoint_invalid_format(self):
        """Test sync endpoint returns 400 for invalid incident ID"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/incidents/INVALID-123/sync-participants/")

        assert response.status_code == 400


@pytest.mark.django_db
class TestIncidentAPIViews:
    """Tests for service API endpoints (not UI)"""

    def setup_method(self):
        """Set up test client and common test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            password="testpass123",
        )
        self.captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            password="testpass123",
        )
        self.reporter = User.objects.create_user(
            username="reporter@example.com",
            email="reporter@example.com",
            password="testpass123",
        )

    def test_create_incident_with_required_fields(self):
        """Test POST /api/incidents/ creates incident with required fields"""
        self.client.force_authenticate(user=self.user)
        data = {
            "title": "New Incident",
            "severity": IncidentSeverity.P1,
            "is_private": False,
            "captain": self.captain.id,
            "reporter": self.reporter.id,
        }
        response = self.client.post("/api/incidents/", data)

        assert response.status_code == 201
        assert Incident.objects.count() == 1

        incident = Incident.objects.first()
        assert incident.title == "New Incident"
        assert incident.severity == IncidentSeverity.P1
        assert incident.is_private is False
        assert incident.captain == self.captain
        assert incident.reporter == self.reporter
        assert incident.status == IncidentStatus.ACTIVE  # Default

    def test_create_incident_with_optional_fields(self):
        """Test creating incident with optional fields"""
        self.client.force_authenticate(user=self.user)
        data = {
            "title": "Detailed Incident",
            "description": "This is a description",
            "impact": "High impact",
            "status": IncidentStatus.MITIGATED,
            "severity": IncidentSeverity.P2,
            "is_private": True,
            "captain": self.captain.id,
            "reporter": self.reporter.id,
        }
        response = self.client.post("/api/incidents/", data)

        assert response.status_code == 201
        incident = Incident.objects.first()
        assert incident.description == "This is a description"
        assert incident.impact == "High impact"
        assert incident.status == IncidentStatus.MITIGATED

    def test_create_incident_missing_required_fields(self):
        """Test creating incident without required fields fails"""
        self.client.force_authenticate(user=self.user)

        # Missing captain
        data = {
            "title": "Incomplete",
            "severity": IncidentSeverity.P1,
            "is_private": False,
            "reporter": self.reporter.id,
        }
        response = self.client.post("/api/incidents/", data)
        assert response.status_code == 400
        assert "captain" in response.data

        # Missing reporter
        data = {
            "title": "Incomplete",
            "severity": IncidentSeverity.P1,
            "is_private": False,
            "captain": self.captain.id,
        }
        response = self.client.post("/api/incidents/", data)
        assert response.status_code == 400
        assert "reporter" in response.data

    def test_list_api_incidents(self):
        """Test GET /api/incidents/ returns all visible incidents"""
        Incident.objects.create(
            title="Public Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=False,
        )
        Incident.objects.create(
            title="Done Incident",
            status=IncidentStatus.DONE,
            severity=IncidentSeverity.P2,
            is_private=False,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/incidents/")

        assert response.status_code == 200
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2

    def test_retrieve_api_incident(self):
        """Test GET /api/incidents/INC-{id}/ returns incident with proper format"""
        incident = Incident.objects.create(
            title="Test Incident",
            description="Description",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=self.captain,
            reporter=self.reporter,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/incidents/{incident.incident_number}/")

        assert response.status_code == 200
        data = response.data
        assert data["id"] == incident.incident_number
        assert data["title"] == "Test Incident"
        assert data["captain"] == self.captain.email
        assert data["reporter"] == self.reporter.email
        assert "created_at" in data
        assert "updated_at" in data

    def test_retrieve_incident_with_null_captain_reporter(self):
        """Test that incidents with null captain/reporter don't crash"""
        incident = Incident.objects.create(
            title="Legacy Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=None,
            reporter=None,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/incidents/{incident.incident_number}/")

        assert response.status_code == 200
        data = response.data
        assert data["captain"] is None
        assert data["reporter"] is None

    def test_update_incident_as_captain(self):
        """Test PATCH /api/incidents/INC-{id}/ allows captain to update"""
        incident = Incident.objects.create(
            title="Original Title",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=self.captain,
            reporter=self.reporter,
        )

        self.client.force_authenticate(user=self.captain)
        data = {"title": "Updated Title"}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", data
        )

        assert response.status_code == 200
        incident.refresh_from_db()
        assert incident.title == "Updated Title"

    def test_update_incident_as_reporter(self):
        """Test reporter can update incident"""
        incident = Incident.objects.create(
            title="Original",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=self.captain,
            reporter=self.reporter,
        )

        self.client.force_authenticate(user=self.reporter)
        data = {"status": IncidentStatus.MITIGATED}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", data
        )

        assert response.status_code == 200
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.MITIGATED

    def test_update_incident_as_participant(self):
        """Test participant can update incident"""
        participant = User.objects.create_user(
            username="participant@example.com",
            email="participant@example.com",
        )
        incident = Incident.objects.create(
            title="Original",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=self.captain,
            reporter=self.reporter,
        )
        incident.participants.add(participant)

        self.client.force_authenticate(user=participant)
        data = {"description": "Updated by participant"}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", data
        )

        assert response.status_code == 200
        incident.refresh_from_db()
        assert incident.description == "Updated by participant"

    def test_update_incident_as_unauthorized_user(self):
        """Test unauthorized user cannot update private incident"""
        incident = Incident.objects.create(
            title="Original",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=self.captain,
            reporter=self.reporter,
            is_private=True,
        )

        self.client.force_authenticate(user=self.user)
        data = {"title": "Hacked"}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", data
        )

        assert (
            response.status_code == 404
        )  # 404 because user can't see private incident
        incident.refresh_from_db()
        assert incident.title == "Original"

    def test_update_incident_as_superuser(self):
        """Test superuser can update any incident"""
        superuser = User.objects.create_superuser(
            username="admin@example.com",
            email="admin@example.com",
            password="testpass123",
        )
        incident = Incident.objects.create(
            title="Original",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=self.captain,
            reporter=self.reporter,
        )

        self.client.force_authenticate(user=superuser)
        data = {"title": "Updated by admin"}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", data
        )

        assert response.status_code == 200
        incident.refresh_from_db()
        assert incident.title == "Updated by admin"

    def test_api_respects_privacy_on_read(self):
        """Test API list respects incident privacy"""
        Incident.objects.create(
            title="Public",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=False,
        )
        Incident.objects.create(
            title="Private - captain",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
            captain=self.user,
        )
        Incident.objects.create(
            title="Private - other",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
            captain=self.captain,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/incidents/")

        assert response.status_code == 200
        assert response.data["count"] == 2
        titles = [inc["title"] for inc in response.data["results"]]
        assert "Public" in titles
        assert "Private - captain" in titles
        assert "Private - other" not in titles

    def test_timestamps_on_create_and_update(self):
        """Test created_at and updated_at timestamps work correctly"""

        self.client.force_authenticate(user=self.captain)

        # Create incident
        payload = {
            "title": "Timestamp Test",
            "severity": "P2",
            "is_private": False,
            "captain": self.captain.id,
            "reporter": self.reporter.id,
        }
        response = self.client.post("/api/incidents/", payload, format="json")
        assert response.status_code == 201

        incident_id = response.json()["id"]

        # Get the incident to check timestamps
        response = self.client.get(f"/api/incidents/{incident_id}/")
        assert response.status_code == 200

        data = response.json()
        created_at = data["created_at"]
        updated_at = data["updated_at"]

        # Verify timestamps exist and are valid ISO 8601 format
        assert created_at is not None
        assert updated_at is not None
        created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        updated_dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        # Initially, created_at and updated_at should be very close (within 1 second)
        assert abs((created_dt - updated_dt).total_seconds()) < 1

        # Wait a bit to ensure timestamps will differ
        time.sleep(0.1)

        # Update the incident
        update_payload = {"status": "Mitigated"}
        response = self.client.patch(
            f"/api/incidents/{incident_id}/", update_payload, format="json"
        )
        assert response.status_code == 200

        # Get the incident again
        response = self.client.get(f"/api/incidents/{incident_id}/")
        data = response.json()

        new_created_at = data["created_at"]
        new_updated_at = data["updated_at"]

        # created_at should remain the same
        assert new_created_at == created_at

        # updated_at should have changed
        assert new_updated_at != updated_at
        assert new_updated_at > updated_at

    def test_create_incident_with_external_links(self):
        """Test creating incident with external links"""
        self.client.force_authenticate(user=self.captain)

        payload = {
            "title": "Incident with Links",
            "severity": "P1",
            "is_private": False,
            "captain": self.captain.id,
            "reporter": self.reporter.id,
            "external_links": {
                "slack": "https://slack.com/channel/123",
                "jira": "https://jira.company.com/browse/INC-1",
            },
        }

        response = self.client.post("/api/incidents/", payload, format="json")
        assert response.status_code == 201

        incident_id = response.json()["id"]

        # Verify links were created
        response = self.client.get(f"/api/incidents/{incident_id}/")
        data = response.json()

        assert data["external_links"]["slack"] == "https://slack.com/channel/123"
        assert data["external_links"]["jira"] == "https://jira.company.com/browse/INC-1"
        assert "datadog" not in data["external_links"]

    def test_add_external_link_via_patch(self):
        """Test adding a single external link via PATCH (merge behavior)"""
        # Create incident with one link
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.ACTIVE,
            captain=self.captain,
            reporter=self.reporter,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/original",
        )

        self.client.force_authenticate(user=self.captain)

        # Add jira link, should keep slack
        payload = {"external_links": {"jira": "https://jira.com/new"}}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", payload, format="json"
        )

        assert response.status_code == 200

        # Verify both links exist
        response = self.client.get(f"/api/incidents/{incident.incident_number}/")
        data = response.json()

        assert data["external_links"]["slack"] == "https://slack.com/original"
        assert data["external_links"]["jira"] == "https://jira.com/new"

    def test_update_existing_external_link(self):
        """Test updating an existing external link via PATCH"""
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.ACTIVE,
            captain=self.captain,
            reporter=self.reporter,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/old",
        )

        self.client.force_authenticate(user=self.captain)

        # Update slack link
        payload = {"external_links": {"slack": "https://slack.com/new"}}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", payload, format="json"
        )

        assert response.status_code == 200

        # Verify link was updated
        response = self.client.get(f"/api/incidents/{incident.incident_number}/")
        data = response.json()

        assert data["external_links"]["slack"] == "https://slack.com/new"

    def test_delete_external_link_with_null(self):
        """Test deleting an external link by sending null"""
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.ACTIVE,
            captain=self.captain,
            reporter=self.reporter,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/test",
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.JIRA,
            url="https://jira.com/test",
        )

        self.client.force_authenticate(user=self.captain)

        # Delete slack link, keep jira
        payload = {"external_links": {"slack": None}}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", payload, format="json"
        )

        assert response.status_code == 200

        # Verify slack deleted, jira remains
        response = self.client.get(f"/api/incidents/{incident.incident_number}/")
        data = response.json()

        assert "slack" not in data["external_links"]
        assert data["external_links"]["jira"] == "https://jira.com/test"

    def test_invalid_external_link_type(self):
        """Test that invalid link types are rejected"""
        self.client.force_authenticate(user=self.captain)

        payload = {
            "title": "Test",
            "severity": "P1",
            "is_private": False,
            "captain": self.captain.id,
            "reporter": self.reporter.id,
            "external_links": {"invalid_type": "https://example.com"},
        }

        response = self.client.post("/api/incidents/", payload, format="json")
        assert response.status_code == 400
        assert "external_links" in response.json()

    def test_invalid_external_link_url(self):
        """Test that invalid URLs are rejected"""
        self.client.force_authenticate(user=self.captain)

        payload = {
            "title": "Test",
            "severity": "P1",
            "is_private": False,
            "captain": self.captain.id,
            "reporter": self.reporter.id,
            "external_links": {"slack": "not-a-valid-url"},
        }

        response = self.client.post("/api/incidents/", payload, format="json")
        assert response.status_code == 400
        assert "external_links" in response.json()

    def test_put_not_allowed(self):
        """Test that PUT returns 405 Method Not Allowed"""
        incident = Incident.objects.create(
            title="Test",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=self.captain,
            reporter=self.reporter,
        )

        self.client.force_authenticate(user=self.captain)
        data = {
            "title": "Updated",
            "severity": "P2",
            "is_private": False,
            "captain": self.captain.id,
            "reporter": self.reporter.id,
        }
        response = self.client.put(f"/api/incidents/{incident.incident_number}/", data)
        assert response.status_code == 405

    def test_patch_without_external_links_preserves_existing(self):
        """Test that PATCH without external_links field preserves existing links"""
        self.client.force_authenticate(user=self.captain)

        # Create incident with external links
        payload = {
            "title": "Test",
            "severity": "P1",
            "is_private": False,
            "captain": self.captain.id,
            "reporter": self.reporter.id,
            "external_links": {
                "slack": "https://slack.com/channel",
                "jira": "https://jira.example.com/issue",
            },
        }
        response = self.client.post("/api/incidents/", payload, format="json")
        assert response.status_code == 201
        incident_id = response.json()["id"]

        # Verify links were created
        response = self.client.get(f"/api/incidents/{incident_id}/")
        assert len(response.json()["external_links"]) == 2

        # PATCH request without external_links should preserve existing
        patch_payload = {"title": "Updated Title"}
        response = self.client.patch(
            f"/api/incidents/{incident_id}/", patch_payload, format="json"
        )
        assert response.status_code == 200

        # Verify links still exist
        response = self.client.get(f"/api/incidents/{incident_id}/")
        data = response.json()
        assert len(data["external_links"]) == 2
        assert data["external_links"]["slack"] == "https://slack.com/channel"
        assert data["external_links"]["jira"] == "https://jira.example.com/issue"

    def test_update_affected_area_tags_via_patch(self):
        """Test setting affected_area_tags via PATCH"""
        Tag.objects.create(name="API", type=TagType.AFFECTED_AREA)
        Tag.objects.create(name="Database", type=TagType.AFFECTED_AREA)

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.ACTIVE,
            captain=self.captain,
            reporter=self.reporter,
        )

        self.client.force_authenticate(user=self.captain)

        payload = {"affected_area_tags": ["API", "Database"]}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", payload, format="json"
        )

        assert response.status_code == 200

        response = self.client.get(f"/api/incidents/{incident.incident_number}/")
        data = response.json()
        assert set(data["affected_area_tags"]) == {"API", "Database"}

    def test_update_root_cause_tags_via_patch(self):
        """Test setting root_cause_tags via PATCH"""
        Tag.objects.create(name="Human Error", type=TagType.ROOT_CAUSE)
        Tag.objects.create(name="Config Change", type=TagType.ROOT_CAUSE)

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.ACTIVE,
            captain=self.captain,
            reporter=self.reporter,
        )

        self.client.force_authenticate(user=self.captain)

        payload = {"root_cause_tags": ["Human Error"]}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", payload, format="json"
        )

        assert response.status_code == 200

        response = self.client.get(f"/api/incidents/{incident.incident_number}/")
        data = response.json()
        assert data["root_cause_tags"] == ["Human Error"]

    def test_replace_existing_tags_via_patch(self):
        """Test that PATCH replaces existing tags"""
        tag1 = Tag.objects.create(name="API", type=TagType.AFFECTED_AREA)
        tag2 = Tag.objects.create(name="Database", type=TagType.AFFECTED_AREA)
        Tag.objects.create(name="Frontend", type=TagType.AFFECTED_AREA)

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.ACTIVE,
            captain=self.captain,
            reporter=self.reporter,
        )
        incident.affected_area_tags.add(tag1, tag2)

        self.client.force_authenticate(user=self.captain)

        # Replace with just Frontend
        payload = {"affected_area_tags": ["Frontend"]}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", payload, format="json"
        )

        assert response.status_code == 200

        response = self.client.get(f"/api/incidents/{incident.incident_number}/")
        data = response.json()
        assert data["affected_area_tags"] == ["Frontend"]

    def test_clear_tags_with_empty_list(self):
        """Test that sending empty list clears all tags"""
        tag = Tag.objects.create(name="API", type=TagType.AFFECTED_AREA)

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.ACTIVE,
            captain=self.captain,
            reporter=self.reporter,
        )
        incident.affected_area_tags.add(tag)

        self.client.force_authenticate(user=self.captain)

        payload = {"affected_area_tags": []}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", payload, format="json"
        )

        assert response.status_code == 200

        response = self.client.get(f"/api/incidents/{incident.incident_number}/")
        data = response.json()
        assert data["affected_area_tags"] == []

    def test_patch_without_tags_preserves_existing(self):
        """Test that PATCH without tag fields preserves existing tags"""
        tag = Tag.objects.create(name="API", type=TagType.AFFECTED_AREA)

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.ACTIVE,
            captain=self.captain,
            reporter=self.reporter,
        )
        incident.affected_area_tags.add(tag)

        self.client.force_authenticate(user=self.captain)

        # PATCH without affected_area_tags field
        payload = {"title": "Updated Title"}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", payload, format="json"
        )

        assert response.status_code == 200

        response = self.client.get(f"/api/incidents/{incident.incident_number}/")
        data = response.json()
        assert data["affected_area_tags"] == ["API"]

    def test_update_tags_nonexistent_tag(self):
        """Test that using a nonexistent tag returns 400"""
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.ACTIVE,
            captain=self.captain,
            reporter=self.reporter,
        )

        self.client.force_authenticate(user=self.captain)

        payload = {"affected_area_tags": ["NonexistentTag"]}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", payload, format="json"
        )

        assert response.status_code == 400

    def test_update_tags_wrong_type(self):
        """Test that using a tag of wrong type returns 400"""
        Tag.objects.create(name="Human Error", type=TagType.ROOT_CAUSE)

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.ACTIVE,
            captain=self.captain,
            reporter=self.reporter,
        )

        self.client.force_authenticate(user=self.captain)

        # Try to use ROOT_CAUSE tag as affected_area_tags
        payload = {"affected_area_tags": ["Human Error"]}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", payload, format="json"
        )

        assert response.status_code == 400

    def test_update_tags_case_insensitive(self):
        """Test that tag matching is case-insensitive"""
        Tag.objects.create(name="API", type=TagType.AFFECTED_AREA)
        Tag.objects.create(name="Database", type=TagType.AFFECTED_AREA)

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.ACTIVE,
            captain=self.captain,
            reporter=self.reporter,
        )

        self.client.force_authenticate(user=self.captain)

        # Use different casing than stored in DB
        payload = {"affected_area_tags": ["api", "DATABASE"]}
        response = self.client.patch(
            f"/api/incidents/{incident.incident_number}/", payload, format="json"
        )

        assert response.status_code == 200

        response = self.client.get(f"/api/incidents/{incident.incident_number}/")
        data = response.json()
        # Should match the tags (preserving original DB casing)
        assert set(data["affected_area_tags"]) == {"API", "Database"}


@pytest.mark.django_db
class TestTagListCreateAPIView:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            password="testpass123",
        )

    def test_list_tags_by_type(self):
        Tag.objects.create(name="API", type=TagType.AFFECTED_AREA)
        Tag.objects.create(name="Database", type=TagType.AFFECTED_AREA)
        Tag.objects.create(name="Human Error", type=TagType.ROOT_CAUSE)

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/tags/?type=AFFECTED_AREA")

        assert response.status_code == 200
        assert len(response.data) == 2
        assert "API" in response.data
        assert "Database" in response.data
        assert "Human Error" not in response.data

    def test_list_root_cause_tags(self):
        Tag.objects.create(name="API", type=TagType.AFFECTED_AREA)
        Tag.objects.create(name="Human Error", type=TagType.ROOT_CAUSE)
        Tag.objects.create(name="Config Change", type=TagType.ROOT_CAUSE)

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/tags/?type=ROOT_CAUSE")

        assert response.status_code == 200
        assert len(response.data) == 2
        assert "Human Error" in response.data
        assert "Config Change" in response.data
        assert "API" not in response.data

    def test_list_tags_missing_type_param(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/tags/")

        assert response.status_code == 400

    def test_list_tags_invalid_type(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/tags/?type=INVALID")

        assert response.status_code == 400

    def test_list_tags_empty_result(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/tags/?type=AFFECTED_AREA")

        assert response.status_code == 200
        assert response.data == []

    def test_create_tag(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/tags/",
            {"name": "New Tag", "type": "AFFECTED_AREA"},
            format="json",
        )

        assert response.status_code == 201
        assert response.data["name"] == "New Tag"
        assert response.data["type"] == "AFFECTED_AREA"
        assert Tag.objects.filter(name="New Tag", type=TagType.AFFECTED_AREA).exists()

    def test_create_tag_root_cause(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/tags/",
            {"name": "Human Error", "type": "ROOT_CAUSE"},
            format="json",
        )

        assert response.status_code == 201
        assert response.data["name"] == "Human Error"
        assert response.data["type"] == "ROOT_CAUSE"
        assert Tag.objects.filter(name="Human Error", type=TagType.ROOT_CAUSE).exists()

    def test_create_tag_missing_name(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/tags/",
            {"type": "AFFECTED_AREA"},
            format="json",
        )

        assert response.status_code == 400

    def test_create_tag_missing_type(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/tags/",
            {"name": "New Tag"},
            format="json",
        )

        assert response.status_code == 400

    def test_create_tag_invalid_type(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/tags/",
            {"name": "New Tag", "type": "INVALID"},
            format="json",
        )

        assert response.status_code == 400

    def test_create_tag_duplicate_case_insensitive(self):
        Tag.objects.create(name="Database", type=TagType.AFFECTED_AREA)

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/tags/",
            {"name": "DATABASE", "type": "AFFECTED_AREA"},
            format="json",
        )

        assert response.status_code == 400

    def test_create_tag_same_name_different_type(self):
        Tag.objects.create(name="Database", type=TagType.AFFECTED_AREA)

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/tags/",
            {"name": "Database", "type": "ROOT_CAUSE"},
            format="json",
        )

        assert response.status_code == 201
        assert Tag.objects.filter(name="Database", type=TagType.ROOT_CAUSE).exists()
