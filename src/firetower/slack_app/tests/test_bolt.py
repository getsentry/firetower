from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from firetower.slack_app.bolt import handle_command

CHANNEL_ID = "C_TEST_CHANNEL"


@pytest.fixture
def user(db):
    u = User.objects.create_user(
        username="test@example.com",
        email="test@example.com",
        first_name="Test",
        last_name="User",
    )
    ExternalProfile.objects.create(
        user=u,
        type=ExternalProfileType.SLACK,
        external_id="U_CAPTAIN",
    )
    return u


@pytest.fixture
def incident(user):
    inc = Incident(
        title="Test Incident",
        severity=IncidentSeverity.P2,
        status=IncidentStatus.ACTIVE,
        captain=user,
        reporter=user,
    )
    inc.save()
    ExternalLink.objects.create(
        incident=inc,
        type=ExternalLinkType.SLACK,
        url="https://slack.com/archives/C_TEST_CHANNEL",
    )
    return inc


@pytest.mark.django_db
class TestRouting:
    @patch("firetower.slack_app.bolt.statsd")
    def test_mitigated_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "mitigated", "channel_id": CHANNEL_ID, "trigger_id": "T123"}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_mitigated_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_mit_alias_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "mit", "channel_id": CHANNEL_ID, "trigger_id": "T123"}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_mitigated_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_resolved_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "resolved", "channel_id": CHANNEL_ID, "trigger_id": "T123"}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_resolved_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_fixed_alias_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "fixed", "channel_id": CHANNEL_ID, "trigger_id": "T123"}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_resolved_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_reopen_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "reopen", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_reopen_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_severity_routes_with_arg(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "severity P0", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_severity_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()
            assert mock_handler.call_args[1]["new_severity"] == "P0"

    @patch("firetower.slack_app.bolt.statsd")
    def test_severity_no_arg_shows_usage(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "severity", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        handle_command(ack=ack, body=body, command=command, respond=respond)

        ack.assert_called_once()
        assert "Usage" in respond.call_args[0][0]

    @patch("firetower.slack_app.bolt.statsd")
    def test_sev_alias_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "sev P1", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_severity_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_subject_routes_with_arg(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "subject New Title Here", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_subject_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()
            assert mock_handler.call_args[1]["new_subject"] == "New Title Here"

    @patch("firetower.slack_app.bolt.statsd")
    def test_subject_no_arg_shows_usage(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "subject", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        handle_command(ack=ack, body=body, command=command, respond=respond)

        ack.assert_called_once()
        assert "Usage" in respond.call_args[0][0]

    @patch("firetower.slack_app.bolt.statsd")
    def test_metrics_for_known_subcommands(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "reopen", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_reopen_command"):
            handle_command(ack=ack, body=body, command=command, respond=respond)

        mock_statsd.increment.assert_any_call(
            "slack_app.commands.submitted", tags=["subcommand:reopen"]
        )

    @patch("firetower.slack_app.bolt.statsd")
    def test_statuspage_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "statuspage", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch(
            "firetower.slack_app.bolt.handle_statuspage_command"
        ) as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_dumpslack_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "dumpslack", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_dumpslack_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()
