from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.hooks import (
    _build_channel_name,
    _build_channel_topic,
    on_captain_changed,
    on_incident_created,
    on_severity_changed,
    on_status_changed,
    on_title_changed,
)
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)


@pytest.mark.django_db
class TestBuildChannelName:
    def test_format(self):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
        )
        assert _build_channel_name(incident) == incident.incident_number.lower()


@pytest.mark.django_db
class TestBuildChannelTopic:
    def test_format_with_captain_slack_profile(self):
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Jane",
            last_name="Doe",
        )
        ExternalProfile.objects.create(
            user=captain,
            type=ExternalProfileType.SLACK,
            external_id="U_CAPTAIN",
        )
        incident = Incident.objects.create(
            title="Database connection pool exhausted",
            severity=IncidentSeverity.P1,
            captain=captain,
        )
        topic = _build_channel_topic(incident)
        assert topic.startswith("[P1] ")
        assert (
            f"|{incident.incident_number} Database connection pool exhausted>" in topic
        )
        assert "| IC: <@U_CAPTAIN>" in topic

    def test_format_with_captain_no_slack_profile(self):
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Jane",
            last_name="Doe",
        )
        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P1,
            captain=captain,
        )
        topic = _build_channel_topic(incident)
        assert "| IC: Jane Doe" in topic

    def test_format_without_captain(self):
        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P2,
        )
        topic = _build_channel_topic(incident)
        assert topic.startswith("[P2] ")
        assert f"|{incident.incident_number} Test Incident>" in topic
        assert "IC:" not in topic

    def test_long_title_is_truncated(self):
        long_title = "A" * 300
        incident = Incident.objects.create(
            title=long_title,
            severity=IncidentSeverity.P1,
        )
        topic = _build_channel_topic(incident)
        assert len(topic) <= 250
        assert "\u2026" in topic


@pytest.mark.django_db
class TestOnIncidentCreated:
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
        )

    @patch("firetower.incidents.hooks._slack_service")
    def test_creates_channel_and_link(self, mock_slack):
        mock_slack.create_channel.return_value = "C99999"
        mock_slack.build_channel_url.return_value = "https://slack.com/archives/C99999"

        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P1,
            captain=self.captain,
            reporter=self.reporter,
        )

        on_incident_created(incident)

        mock_slack.create_channel.assert_called_once_with(
            incident.incident_number.lower()
        )
        link = ExternalLink.objects.get(incident=incident, type=ExternalLinkType.SLACK)
        assert link.url == "https://slack.com/archives/C99999"
        mock_slack.set_channel_topic.assert_called_once()
        mock_slack.add_bookmark.assert_called_once()
        mock_slack.post_message.assert_called_once()

    @patch("firetower.incidents.hooks._slack_service")
    def test_skips_if_slack_link_exists(self, mock_slack):
        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P1,
            captain=self.captain,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C00000",
        )

        on_incident_created(incident)

        mock_slack.create_channel.assert_not_called()

    @patch("firetower.incidents.hooks._slack_service")
    def test_handles_create_channel_failure(self, mock_slack):
        mock_slack.create_channel.return_value = None

        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P1,
        )

        on_incident_created(incident)

        assert not ExternalLink.objects.filter(
            incident=incident, type=ExternalLinkType.SLACK
        ).exists()

    @patch("firetower.incidents.hooks._slack_service")
    def test_invites_captain_with_slack_profile(self, mock_slack):
        mock_slack.create_channel.return_value = "C99999"
        mock_slack.build_channel_url.return_value = "https://slack.com/archives/C99999"

        ExternalProfile.objects.create(
            user=self.captain,
            type=ExternalProfileType.SLACK,
            external_id="U_CAPTAIN",
        )

        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P1,
            captain=self.captain,
        )

        on_incident_created(incident)

        mock_slack.invite_to_channel.assert_called_once_with("C99999", ["U_CAPTAIN"])


@pytest.mark.django_db
class TestOnStatusChanged:
    @patch("firetower.incidents.hooks._slack_service")
    def test_posts_and_updates_topic(self, mock_slack):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.MITIGATED,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_status_changed(incident, IncidentStatus.ACTIVE)

        mock_slack.post_message.assert_called_once()
        assert "Active" in mock_slack.post_message.call_args[0][1]
        assert "Mitigated" in mock_slack.post_message.call_args[0][1]
        mock_slack.set_channel_topic.assert_not_called()

    @patch("firetower.incidents.hooks._slack_service")
    def test_noop_without_slack_link(self, mock_slack):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
        )

        on_status_changed(incident, IncidentStatus.ACTIVE)

        mock_slack.post_message.assert_not_called()


@pytest.mark.django_db
class TestOnSeverityChanged:
    @patch("firetower.incidents.hooks._slack_service")
    def test_posts_and_updates_topic(self, mock_slack):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P0,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_severity_changed(incident, IncidentSeverity.P2)

        mock_slack.post_message.assert_called_once()
        assert "P2" in mock_slack.post_message.call_args[0][1]
        assert "P0" in mock_slack.post_message.call_args[0][1]
        mock_slack.set_channel_topic.assert_called_once()

    @patch("firetower.incidents.hooks._slack_service")
    def test_noop_without_slack_link(self, mock_slack):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
        )

        on_severity_changed(incident, IncidentSeverity.P2)

        mock_slack.post_message.assert_not_called()


@pytest.mark.django_db
class TestOnTitleChanged:
    @patch("firetower.incidents.hooks._slack_service")
    def test_updates_topic(self, mock_slack):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        incident = Incident.objects.create(
            title="Updated Title",
            severity=IncidentSeverity.P1,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_title_changed(incident)

        mock_slack.set_channel_topic.assert_called_once()

    @patch("firetower.incidents.hooks._slack_service")
    def test_noop_without_slack_link(self, mock_slack):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
        )

        on_title_changed(incident)

        mock_slack.set_channel_topic.assert_not_called()


@pytest.mark.django_db
class TestOnCaptainChanged:
    @patch("firetower.incidents.hooks._slack_service")
    def test_updates_topic_and_invites(self, mock_slack):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        captain = User.objects.create_user(
            username="newcaptain@example.com",
            email="newcaptain@example.com",
            first_name="New",
            last_name="Captain",
        )
        ExternalProfile.objects.create(
            user=captain,
            type=ExternalProfileType.SLACK,
            external_id="U_NEW",
        )

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            captain=captain,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_captain_changed(incident)

        mock_slack.set_channel_topic.assert_called_once()
        mock_slack.post_message.assert_called_once()
        assert "<@U_NEW>" in mock_slack.post_message.call_args[0][1]
        mock_slack.invite_to_channel.assert_called_once_with("C12345", ["U_NEW"])

    @patch("firetower.incidents.hooks._slack_service")
    def test_noop_without_slack_link(self, mock_slack):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
        )

        on_captain_changed(incident)

        mock_slack.set_channel_topic.assert_not_called()
