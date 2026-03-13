from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.models import User

from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    Tag,
    TagType,
)
from firetower.incidents.serializers import (
    IncidentDetailUISerializer,
    IncidentListUISerializer,
    IncidentWriteSerializer,
)


@pytest.mark.django_db
class TestIncidentListUISerializer:
    def test_incident_list_serialization(self):
        """Test incident serialization for list view"""
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Jane",
            last_name="Captain",
        )
        reporter = User.objects.create_user(
            username="reporter@example.com",
            email="reporter@example.com",
            first_name="John",
            last_name="Reporter",
        )

        incident = Incident.objects.create(
            title="Test Incident",
            description="Test description",
            impact_summary="Test impact",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=False,
            captain=captain,
            reporter=reporter,
        )

        # Add tags
        area_tag = Tag.objects.create(name="API", type=TagType.AFFECTED_SERVICE)
        cause_tag = Tag.objects.create(name="Database", type=TagType.ROOT_CAUSE)
        incident.affected_service_tags.add(area_tag)
        incident.root_cause_tags.add(cause_tag)

        serializer = IncidentListUISerializer(incident)
        data = serializer.data

        # Check id is incident_number string (frontend compatibility)
        assert data["id"] == f"{settings.PROJECT_KEY}-{incident.id}"
        assert data["title"] == "Test Incident"
        assert data["status"] == IncidentStatus.ACTIVE
        assert data["severity"] == IncidentSeverity.P1


@pytest.mark.django_db
class TestIncidentDetailUISerializer:
    def test_incident_detail_serialization(self):
        """Test incident serialization for detail view (matches frontend expectations)"""
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Jane",
            last_name="Captain",
        )
        reporter = User.objects.create_user(
            username="reporter@example.com",
            email="reporter@example.com",
            first_name="John",
            last_name="Reporter",
        )
        participant = User.objects.create_user(
            username="participant@example.com",
            email="participant@example.com",
            first_name="Alice",
            last_name="Participant",
        )

        incident = Incident.objects.create(
            title="Test Incident",
            description="Test description",
            status=IncidentStatus.MITIGATED,
            severity=IncidentSeverity.P2,
            captain=captain,
            reporter=reporter,
        )
        incident.participants.add(participant)

        # Add tags
        area_tag = Tag.objects.create(name="API", type=TagType.AFFECTED_SERVICE)
        cause_tag = Tag.objects.create(name="Database", type=TagType.ROOT_CAUSE)
        incident.affected_service_tags.add(area_tag)
        incident.root_cause_tags.add(cause_tag)

        # Add external links
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/channels/incident-123",
        )

        serializer = IncidentDetailUISerializer(incident)
        data = serializer.data

        # Check id is incident_number string (frontend compatibility)
        assert data["id"] == f"{settings.PROJECT_KEY}-{incident.id}"
        assert data["title"] == "Test Incident"

        # Check participants include captain, reporter, and other participants with roles
        assert len(data["participants"]) == 3

        # First should be captain
        assert data["participants"][0]["name"] == "Jane Captain"
        assert data["participants"][0]["role"] == "Captain"
        assert "avatar_url" in data["participants"][0]

        # Second should be reporter
        assert data["participants"][1]["name"] == "John Reporter"
        assert data["participants"][1]["role"] == "Reporter"
        assert "avatar_url" in data["participants"][1]

        # Third should be participant
        assert data["participants"][2]["name"] == "Alice Participant"
        assert data["participants"][2]["role"] == "Participant"
        assert "avatar_url" in data["participants"][2]

        # Check affected_service_tags and root_cause_tags as arrays of strings
        assert "API" in data["affected_service_tags"]
        assert "Database" in data["root_cause_tags"]

        # Check external links (dict format for frontend compatibility, only includes existing links)
        assert "slack" in data["external_links"]
        assert (
            data["external_links"]["slack"] == "https://slack.com/channels/incident-123"
        )
        assert "jira" not in data["external_links"]  # Not set, so not included
        assert len(data["external_links"]) == 1


@pytest.mark.django_db
class TestIncidentWriteSerializerSlackSync:
    @pytest.fixture
    def incident(self):
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Jane",
            last_name="Captain",
        )
        reporter = User.objects.create_user(
            username="reporter@example.com",
            email="reporter@example.com",
            first_name="John",
            last_name="Reporter",
        )
        return Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=captain,
            reporter=reporter,
        )

    @pytest.fixture
    def new_captain(self):
        return User.objects.create_user(
            username="newcaptain@example.com",
            email="newcaptain@example.com",
            first_name="New",
            last_name="Captain",
        )

    @patch("firetower.incidents.serializers.sync_incident_to_slack")
    def test_syncs_on_title_change(self, mock_sync, incident):
        serializer = IncidentWriteSerializer(
            incident, data={"title": "New Title"}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        mock_sync.assert_called_once_with(incident)

    @patch("firetower.incidents.serializers.sync_incident_to_slack")
    def test_syncs_on_severity_change(self, mock_sync, incident):
        serializer = IncidentWriteSerializer(
            incident, data={"severity": IncidentSeverity.P2}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        mock_sync.assert_called_once_with(incident)

    @patch("firetower.incidents.serializers.sync_incident_to_slack")
    def test_syncs_on_captain_change(self, mock_sync, incident, new_captain):
        serializer = IncidentWriteSerializer(
            incident, data={"captain": new_captain.email}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        mock_sync.assert_called_once_with(incident)

    @patch("firetower.incidents.serializers.sync_incident_to_slack")
    def test_does_not_sync_on_description_change(self, mock_sync, incident):
        serializer = IncidentWriteSerializer(
            incident, data={"description": "Updated description"}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        mock_sync.assert_not_called()

    @patch("firetower.incidents.serializers.sync_incident_to_slack")
    def test_does_not_sync_on_status_change(self, mock_sync, incident):
        serializer = IncidentWriteSerializer(
            incident, data={"status": IncidentStatus.MITIGATED}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        mock_sync.assert_not_called()
