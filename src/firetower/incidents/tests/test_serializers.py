import pytest
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
            impact="Test impact",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=False,
            captain=captain,
            reporter=reporter,
        )

        # Add tags
        area_tag = Tag.objects.create(name="API", type=TagType.AFFECTED_AREA)
        cause_tag = Tag.objects.create(name="Database", type=TagType.ROOT_CAUSE)
        incident.affected_area_tags.add(area_tag)
        incident.root_cause_tags.add(cause_tag)

        serializer = IncidentListUISerializer(incident)
        data = serializer.data

        # Check id is incident_number string (frontend compatibility)
        assert data["id"] == f"INC-{incident.id}"
        assert data["title"] == "Test Incident"
        assert data["status"] == IncidentStatus.ACTIVE
        assert data["severity"] == IncidentSeverity.P1


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
        area_tag = Tag.objects.create(name="API", type=TagType.AFFECTED_AREA)
        cause_tag = Tag.objects.create(name="Database", type=TagType.ROOT_CAUSE)
        incident.affected_area_tags.add(area_tag)
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
        assert data["id"] == f"INC-{incident.id}"
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

        # Check affected_areas and root_causes as arrays of strings
        assert "API" in data["affected_areas"]
        assert "Database" in data["root_causes"]

        # Check external links (dict format for frontend compatibility)
        assert "slack" in data["external_links"]
        assert (
            data["external_links"]["slack"] == "https://slack.com/channels/incident-123"
        )
        assert data["external_links"]["jira"] is None  # Not set
