from unittest.mock import MagicMock, patch

import pytest

from firetower.slack_app.bolt import handle_command
from firetower.slack_app.handlers.captain import (
    handle_captain_command,
    handle_captain_submission,
)

from .conftest import CHANNEL_ID


@pytest.mark.django_db
class TestCaptainCommand:
    def test_opens_modal(self, incident):
        ack = MagicMock()
        body = {
            "channel_id": CHANNEL_ID,
            "trigger_id": "T123",
        }
        command = {"command": "/ft"}
        respond = MagicMock()

        with patch("firetower.slack_app.bolt.get_bolt_app") as mock_app:
            handle_captain_command(ack, body, command, respond)

            ack.assert_called_once()
            mock_app.return_value.client.views_open.assert_called_once()
            view = mock_app.return_value.client.views_open.call_args[1]["view"]
            assert view["callback_id"] == "captain_incident_modal"

    def test_prefills_current_captain(self, user, incident):
        ack = MagicMock()
        body = {
            "channel_id": CHANNEL_ID,
            "trigger_id": "T123",
        }
        command = {"command": "/ft"}
        respond = MagicMock()

        with patch("firetower.slack_app.bolt.get_bolt_app") as mock_app:
            handle_captain_command(ack, body, command, respond)

            view = mock_app.return_value.client.views_open.call_args[1]["view"]
            captain_element = view["blocks"][0]["element"]
            assert captain_element["initial_user"] == "U_CAPTAIN"

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN", "trigger_id": "T123"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_captain_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]

    def test_no_trigger_id(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_captain_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "trigger_id" in respond.call_args[0][0]


@pytest.mark.django_db
class TestCaptainSubmission:
    @patch("firetower.incidents.serializers.on_captain_changed")
    @patch("firetower.incidents.serializers.on_title_changed")
    @patch("firetower.slack_app.handlers.captain.get_or_create_user_from_slack_id")
    def test_sets_captain(
        self, mock_get_user, mock_title_hook, mock_captain_hook, user, incident
    ):
        mock_get_user.return_value = user
        ack = MagicMock()
        body = {"user": {"id": "U_SUBMITTER"}}
        view = {
            "state": {
                "values": {
                    "captain_block": {"captain_select": {"selected_user": "U_CAPTAIN"}}
                }
            },
            "private_metadata": CHANNEL_ID,
        }
        client = MagicMock()

        handle_captain_submission(ack, body, view, client)

        ack.assert_called_once()
        incident.refresh_from_db()
        assert incident.captain == user
        client.chat_postMessage.assert_not_called()

    @patch("firetower.slack_app.handlers.captain.get_or_create_user_from_slack_id")
    def test_user_not_found(self, mock_get_user, incident):
        mock_get_user.return_value = None
        ack = MagicMock()
        body = {"user": {"id": "U_SUBMITTER"}}
        view = {
            "state": {
                "values": {
                    "captain_block": {"captain_select": {"selected_user": "U_UNKNOWN"}}
                }
            },
            "private_metadata": CHANNEL_ID,
        }
        client = MagicMock()

        handle_captain_submission(ack, body, view, client)

        ack.assert_called_once()
        assert "Failed to resolve" in client.chat_postMessage.call_args[1]["text"]

    def test_no_captain_selected(self, incident):
        ack = MagicMock()
        body = {"user": {"id": "U_SUBMITTER"}}
        view = {
            "state": {
                "values": {"captain_block": {"captain_select": {"selected_user": None}}}
            },
            "private_metadata": CHANNEL_ID,
        }
        client = MagicMock()

        handle_captain_submission(ack, body, view, client)

        ack.assert_called_once()
        assert "not changed" in client.chat_postMessage.call_args[1]["text"]


@pytest.mark.django_db
class TestCaptainRouting:
    @patch("firetower.slack_app.bolt.statsd")
    def test_captain_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "captain", "channel_id": CHANNEL_ID, "trigger_id": "T123"}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_captain_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_ic_alias_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "ic", "channel_id": CHANNEL_ID, "trigger_id": "T123"}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_captain_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_captain_with_args_still_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {
            "text": "captain <@U_CAPTAIN>",
            "channel_id": CHANNEL_ID,
            "trigger_id": "T123",
        }
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_captain_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()
