from unittest.mock import MagicMock, patch

import pytest

from firetower.slack_app.bolt import handle_command
from firetower.slack_app.handlers.captain import handle_captain_command

from .conftest import CHANNEL_ID


@pytest.mark.django_db
class TestCaptainCommand:
    @patch("firetower.incidents.serializers.on_captain_changed")
    @patch("firetower.incidents.serializers.on_title_changed")
    @patch("firetower.slack_app.handlers.captain.get_or_create_user_from_slack_id")
    def test_sets_captain(
        self, mock_get_user, mock_title_hook, mock_captain_hook, user, incident
    ):
        mock_get_user.return_value = user
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_captain_command(ack, body, command, respond, user_mention="<@U_CAPTAIN>")

        ack.assert_called_once()
        incident.refresh_from_db()
        assert incident.captain == user
        assert "captain updated" in respond.call_args[0][0]

    def test_no_user_mention(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_captain_command(ack, body, command, respond, user_mention="notamention")

        ack.assert_called_once()
        assert "Usage" in respond.call_args[0][0]

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_captain_command(ack, body, command, respond, user_mention="<@U_CAPTAIN>")

        ack.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]

    @patch("firetower.slack_app.handlers.captain.get_or_create_user_from_slack_id")
    def test_user_not_found(self, mock_get_user, incident):
        mock_get_user.return_value = None
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_captain_command(ack, body, command, respond, user_mention="<@U_UNKNOWN>")

        ack.assert_called_once()
        assert "Could not resolve" in respond.call_args[0][0]


@pytest.mark.django_db
class TestCaptainRouting:
    @patch("firetower.slack_app.bolt.statsd")
    def test_captain_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "captain <@U_CAPTAIN>", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_captain_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()
            assert mock_handler.call_args[1]["user_mention"] == "<@U_CAPTAIN>"

    @patch("firetower.slack_app.bolt.statsd")
    def test_ic_alias_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "ic <@U_CAPTAIN>", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_captain_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_captain_no_arg_shows_usage(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "captain", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        handle_command(ack=ack, body=body, command=command, respond=respond)

        ack.assert_called_once()
        assert "Usage" in respond.call_args[0][0]
