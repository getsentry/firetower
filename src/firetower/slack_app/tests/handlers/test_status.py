from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from firetower.incidents.models import IncidentStatus
from firetower.slack_app.bolt import handle_command
from firetower.slack_app.handlers.status import handle_status_command

from .conftest import CHANNEL_ID


@pytest.mark.django_db
class TestStatusCommand:
    def test_shows_incident_info(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/inc"}
        respond = MagicMock()

        handle_status_command(ack, body, command, respond)

        ack.assert_called_once()
        text = respond.call_args[0][0]
        assert "INC-" in text
        assert "Active" in text
        assert "P2" in text
        assert "Test Incident" in text

    def test_shows_ic_as_slack_mention(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/inc"}
        respond = MagicMock()

        handle_status_command(ack, body, command, respond)

        text = respond.call_args[0][0]
        assert "<@U_CAPTAIN>" in text

    def test_no_captain_shows_unassigned(self, user, incident):
        incident.captain = None
        incident.save()
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/inc"}
        respond = MagicMock()

        handle_status_command(ack, body, command, respond)

        text = respond.call_args[0][0]
        assert "unassigned" in text

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN"}
        command = {"command": "/inc"}
        respond = MagicMock()

        handle_status_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]

    def test_mitigated_shows_mitigated_time(self, incident):
        mitigated_at = timezone.now()
        incident.status = IncidentStatus.MITIGATED
        incident.time_mitigated = mitigated_at
        incident.save()

        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/inc"}
        respond = MagicMock()

        handle_status_command(ack, body, command, respond)

        text = respond.call_args[0][0]
        assert "Mitigated" in text
        assert "Mitigated:" in text

    def test_mitigated_status_without_time(self, incident):
        incident.status = IncidentStatus.MITIGATED
        incident.time_mitigated = None
        incident.save()

        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/inc"}
        respond = MagicMock()

        handle_status_command(ack, body, command, respond)

        text = respond.call_args[0][0]
        assert "Mitigated" in text
        assert "Mitigated:" not in text

    def test_includes_firetower_link(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/inc"}
        respond = MagicMock()

        with patch("firetower.slack_app.handlers.status.settings") as mock_settings:
            mock_settings.FIRETOWER_BASE_URL = "https://firetower.example.com"
            handle_status_command(ack, body, command, respond)

        text = respond.call_args[0][0]
        assert "https://firetower.example.com" in text


@pytest.mark.django_db
class TestStatusRouting:
    @patch("firetower.slack_app.bolt.statsd")
    def test_status_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "status", "channel_id": CHANNEL_ID}
        command = {"command": "/inc"}

        with patch("firetower.slack_app.bolt.handle_status_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()
