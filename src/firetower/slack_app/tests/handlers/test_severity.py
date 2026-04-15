from unittest.mock import MagicMock, patch

import pytest

from firetower.incidents.models import IncidentSeverity
from firetower.slack_app.handlers.severity import handle_severity_command

from .conftest import CHANNEL_ID


@pytest.mark.django_db
class TestSeverityCommand:
    @patch("firetower.incidents.serializers.on_severity_changed")
    @patch("firetower.incidents.serializers.on_title_changed")
    def test_changes_severity(self, mock_title_hook, mock_sev_hook, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_severity_command(ack, body, command, respond, new_severity="P0")

        ack.assert_called_once()
        incident.refresh_from_db()
        assert incident.severity == IncidentSeverity.P0
        assert "P0" in respond.call_args[0][0]

    def test_invalid_severity(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_severity_command(ack, body, command, respond, new_severity="P9")

        ack.assert_called_once()
        assert "Invalid severity" in respond.call_args[0][0]

    def test_case_insensitive(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        with patch("firetower.incidents.serializers.on_severity_changed"):
            handle_severity_command(ack, body, command, respond, new_severity="p1")

        incident.refresh_from_db()
        assert incident.severity == IncidentSeverity.P1

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_severity_command(ack, body, command, respond, new_severity="P0")

        ack.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]
