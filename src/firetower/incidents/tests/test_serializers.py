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

        # List view should not include captain/reporter/tags
        assert "captain" not in data
        assert "reporter" not in data
        assert "affected_areas" not in data
        assert "root_causes" not in data


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

        # Check nested users for captain/reporter (name and avatar only)
        assert data["captain"]["name"] == "Jane Captain"
        assert "avatar_url" in data["captain"]
        assert "email" not in data["captain"]

        assert data["reporter"]["name"] == "John Reporter"
        assert "avatar_url" in data["reporter"]
        assert "email" not in data["reporter"]

        # Check participants structure (matches frontend expectation)
        assert len(data["participants"]) == 3  # captain, reporter, participant

        # Find each participant
        captain_participant = next(
            p for p in data["participants"] if p["role"] == "Captain"
        )
        assert captain_participant["name"] == "Jane Captain"
        assert "avatar_url" in captain_participant

        reporter_participant = next(
            p for p in data["participants"] if p["role"] == "Reporter"
        )
        assert reporter_participant["name"] == "John Reporter"

        other_participant = next(
            p for p in data["participants"] if p["role"] == "Participant"
        )
        assert other_participant["name"] == "Alice Participant"

        # Check affected_areas and root_causes as arrays of strings
        assert "API" in data["affected_areas"]
        assert "Database" in data["root_causes"]

        # Check external links (dict format for frontend compatibility)
        assert "slack" in data["external_links"]
        assert (
            data["external_links"]["slack"] == "https://slack.com/channels/incident-123"
        )
        assert data["external_links"]["jira"] is None  # Not set
