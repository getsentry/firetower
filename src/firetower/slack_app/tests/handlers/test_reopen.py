from unittest.mock import MagicMock, patch

import pytest

from firetower.incidents.models import IncidentStatus
from firetower.slack_app.handlers.reopen import handle_reopen_command

from .conftest import CHANNEL_ID


@pytest.mark.django_db
class TestReopenCommand:
    @patch("firetower.incidents.serializers.on_status_changed")
    @patch("firetower.incidents.serializers.on_title_changed")
    def test_reopens_mitigated_incident(
        self, mock_title_hook, mock_status_hook, incident
    ):
        incident.status = IncidentStatus.MITIGATED
        incident.save()

        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_reopen_command(ack, body, command, respond)

        ack.assert_called_once()
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.ACTIVE
        assert "reopened" in respond.call_args[0][0]

    def test_already_active_responds(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_reopen_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "already Active" in respond.call_args[0][0]

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_reopen_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]
