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
class TestIncidentWriteSerializerHooks:
    @pytest.fixture(autouse=True)
    def enable_hooks(self, settings):
        settings.HOOKS_ENABLED = True

    def setup_method(self):
        self.captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Jane",
            last_name="Captain",
        )
        self.reporter = User.objects.create_user(
            username="reporter@example.com",
            email="reporter@example.com",
            first_name="John",
            last_name="Reporter",
        )

    @patch("firetower.incidents.serializers.on_incident_created")
    def test_create_calls_on_incident_created(self, mock_hook):
        serializer = IncidentWriteSerializer(
            data={
                "title": "Test",
                "severity": "P1",
                "captain": "captain@example.com",
                "reporter": "reporter@example.com",
            }
        )
        assert serializer.is_valid(), serializer.errors
        incident = serializer.save()
        mock_hook.assert_called_once_with(incident)

    @patch("firetower.incidents.serializers.on_status_changed")
    def test_update_calls_on_status_changed(self, mock_hook):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.ACTIVE,
            captain=self.captain,
            reporter=self.reporter,
        )
        serializer = IncidentWriteSerializer(
            instance=incident,
            data={"status": "Mitigated"},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        mock_hook.assert_called_once_with(incident, IncidentStatus.ACTIVE)

    @patch("firetower.incidents.serializers.on_severity_changed")
    def test_update_calls_on_severity_changed(self, mock_hook):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P2,
            captain=self.captain,
            reporter=self.reporter,
        )
        serializer = IncidentWriteSerializer(
            instance=incident,
            data={"severity": "P0"},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        mock_hook.assert_called_once_with(incident, IncidentSeverity.P2)

    @patch("firetower.incidents.serializers.on_captain_changed")
    def test_update_calls_on_captain_changed(self, mock_hook):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            captain=self.captain,
            reporter=self.reporter,
        )
        User.objects.create_user(
            username="new@example.com",
            email="new@example.com",
        )
        serializer = IncidentWriteSerializer(
            instance=incident,
            data={"captain": "new@example.com"},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        mock_hook.assert_called_once_with(incident)

    @patch("firetower.incidents.serializers.on_status_changed")
    @patch("firetower.incidents.serializers.on_severity_changed")
    @patch("firetower.incidents.serializers.on_captain_changed")
    def test_update_no_hooks_when_fields_unchanged(
        self, mock_captain, mock_severity, mock_status
    ):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            captain=self.captain,
            reporter=self.reporter,
        )
        serializer = IncidentWriteSerializer(
            instance=incident,
            data={"title": "Updated Title"},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        mock_status.assert_not_called()
        mock_severity.assert_not_called()
        mock_captain.assert_not_called()

    @patch("firetower.incidents.hooks._slack_service")
    def test_update_same_status_string_does_not_fire_hook(self, mock_slack):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.ACTIVE,
            captain=self.captain,
            reporter=self.reporter,
        )
        serializer = IncidentWriteSerializer(
            instance=incident,
            data={"status": "Active"},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        mock_slack.post_message.assert_not_called()

    @patch("firetower.incidents.hooks._slack_service")
    def test_update_different_status_string_fires_hook(self, mock_slack):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"
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
            url="https://slack.com/archives/C12345",
        )
        serializer = IncidentWriteSerializer(
            instance=incident,
            data={"status": "Mitigated"},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        mock_slack.post_message.assert_called_once()
        msg = mock_slack.post_message.call_args[0][1]
        assert "Active" in msg
        assert "Mitigated" in msg
