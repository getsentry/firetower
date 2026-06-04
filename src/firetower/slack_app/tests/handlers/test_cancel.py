from unittest.mock import MagicMock, patch

import pytest

from firetower.incidents.models import IncidentStatus
from firetower.slack_app.handlers.cancel import (
    handle_cancel_command,
    handle_cancel_submission,
)

from .conftest import CHANNEL_ID


@pytest.mark.django_db
class TestCancelCommand:
    @patch("firetower.slack_app.bolt.get_bolt_app")
    def test_opens_modal(self, mock_get_bolt_app, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID, "trigger_id": "T12345"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_cancel_command(ack, body, command, respond)

        ack.assert_called_once()
        mock_get_bolt_app.return_value.client.views_open.assert_called_once()
        view = mock_get_bolt_app.return_value.client.views_open.call_args[1]["view"]
        assert view["callback_id"] == "cancel_incident_modal"
        assert view["private_metadata"] == CHANNEL_ID

    @patch("firetower.slack_app.bolt.get_bolt_app")
    @patch("firetower.incidents.serializers.on_incident_updated")
    def test_already_canceled_does_not_open_modal(
        self, mock_updated_hook, mock_get_bolt_app, incident
    ):
        incident.status = IncidentStatus.CANCELED
        incident.save()

        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID, "trigger_id": "T12345"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_cancel_command(ack, body, command, respond)

        ack.assert_called_once()
        mock_get_bolt_app.return_value.client.views_open.assert_not_called()
        assert "already Canceled" in respond.call_args[0][0]

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN", "trigger_id": "T12345"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_cancel_command(ack, body, command, respond)

        ack.assert_called_once()
        respond.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]


@pytest.mark.django_db
class TestCancelSubmission:
    @patch("firetower.incidents.serializers.on_incident_updated")
    def test_transitions_to_canceled(self, mock_updated_hook, incident):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "reason_block": {"reason": {"value": "Duplicate of INC-123"}},
                }
            },
        }

        handle_cancel_submission(ack, body, view, client)

        ack.assert_called_once()
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.CANCELED
        client.chat_postMessage.assert_called_once()
        msg = client.chat_postMessage.call_args[1]["text"]
        assert "Canceled" in msg
        assert "Duplicate of INC-123" in msg
        assert "<@U_CAPTAIN>" in msg

    def test_empty_reason_returns_errors(self, incident):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "reason_block": {"reason": {"value": "   "}},
                }
            },
        }

        handle_cancel_submission(ack, body, view, client)

        ack.assert_called_once_with(
            response_action="errors",
            errors={"reason_block": "A reason is required."},
        )
        incident.refresh_from_db()
        assert incident.status != IncidentStatus.CANCELED
        client.chat_postMessage.assert_not_called()

    @patch("firetower.incidents.serializers.on_incident_updated")
    def test_already_canceled_is_noop(self, mock_updated_hook, incident):
        incident.status = IncidentStatus.CANCELED
        incident.save()

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "reason_block": {"reason": {"value": "Duplicate of INC-123"}},
                }
            },
        }

        handle_cancel_submission(ack, body, view, client)

        ack.assert_called_once()
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.CANCELED
        client.chat_postMessage.assert_not_called()

    @patch("firetower.incidents.serializers.on_incident_updated")
    @patch("firetower.slack_app.handlers.cancel.IncidentWriteSerializer")
    def test_invalid_serializer_posts_failure(
        self, mock_serializer_cls, mock_updated_hook, incident
    ):
        serializer = mock_serializer_cls.return_value
        serializer.is_valid.return_value = False
        serializer.errors = {"status": ["bad"]}

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "reason_block": {"reason": {"value": "some reason"}},
                }
            },
        }

        handle_cancel_submission(ack, body, view, client)

        serializer.save.assert_not_called()
        client.chat_postMessage.assert_called_once()
        assert "Failed to cancel" in client.chat_postMessage.call_args[1]["text"]

    def test_missing_incident_does_not_crash(self, db):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = {
            "private_metadata": "C_NONEXISTENT",
            "state": {
                "values": {
                    "reason_block": {"reason": {"value": "some reason"}},
                }
            },
        }

        handle_cancel_submission(ack, body, view, client)

        ack.assert_called_once()
        client.chat_postMessage.assert_not_called()
