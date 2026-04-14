from unittest.mock import MagicMock, patch

import pytest

from firetower.incidents.models import IncidentStatus
from firetower.slack_app.handlers.mitigated import (
    handle_mitigated_command,
    handle_mitigated_submission,
)

from .conftest import CHANNEL_ID


@pytest.mark.django_db
class TestMitigatedCommand:
    @patch("firetower.slack_app.bolt.get_bolt_app")
    def test_opens_modal(self, mock_get_bolt_app, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID, "trigger_id": "T12345"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_mitigated_command(ack, body, command, respond)

        ack.assert_called_once()
        mock_get_bolt_app.return_value.client.views_open.assert_called_once()
        view = mock_get_bolt_app.return_value.client.views_open.call_args[1]["view"]
        assert view["callback_id"] == "mitigated_incident_modal"
        assert view["private_metadata"] == CHANNEL_ID
        assert incident.incident_number in view["title"]["text"]

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN", "trigger_id": "T12345"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_mitigated_command(ack, body, command, respond)

        ack.assert_called_once()
        respond.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]


@pytest.mark.django_db
class TestMitigatedSubmission:
    @patch("firetower.incidents.serializers.on_status_changed")
    @patch("firetower.incidents.serializers.on_title_changed")
    def test_transitions_to_mitigated(
        self, mock_title_hook, mock_status_hook, incident
    ):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "impact_block": {"impact_update": {"value": "Reduced impact"}},
                    "todo_block": {"todo_update": {"value": "Monitor overnight"}},
                }
            },
        }

        handle_mitigated_submission(ack, body, view, client)

        ack.assert_called_once()
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.MITIGATED
        assert "Reduced impact" in incident.description
        assert "Monitor overnight" in incident.description
        client.chat_postMessage.assert_called_once()
        msg = client.chat_postMessage.call_args[1]["text"]
        assert "Mitigated" in msg

    def test_missing_incident_does_not_crash(self, db):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = {
            "private_metadata": "C_NONEXISTENT",
            "state": {
                "values": {
                    "impact_block": {"impact_update": {"value": "x"}},
                    "todo_block": {"todo_update": {"value": "y"}},
                }
            },
        }

        handle_mitigated_submission(ack, body, view, client)

        ack.assert_called_once()
        client.chat_postMessage.assert_not_called()
