from unittest.mock import MagicMock, patch

import pytest

from firetower.slack_app.handlers.subject import handle_subject_command

from .conftest import CHANNEL_ID


@pytest.mark.django_db
class TestSubjectCommand:
    @patch("firetower.incidents.serializers.on_title_changed")
    def test_updates_title(self, mock_title_hook, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_subject_command(ack, body, command, respond, new_subject="New Title")

        ack.assert_called_once()
        incident.refresh_from_db()
        assert incident.title == "New Title"
        assert "New Title" in respond.call_args[0][0]

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_subject_command(ack, body, command, respond, new_subject="New Title")

        ack.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]
