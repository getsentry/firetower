from unittest.mock import MagicMock, call, patch

import pytest

from firetower.slack_app.bolt import handle_inc


class TestHandleInc:
    def _make_body(self, text="", command="/inc"):
        return {"text": text, "command": command}

    def _make_command(self, command="/inc", text=""):
        return {"command": command, "text": text}

    @patch("firetower.slack_app.bolt.statsd")
    def test_help_returns_help_text(self, mock_statsd):
        ack = MagicMock()
        respond = MagicMock()
        body = self._make_body(text="help")
        command = self._make_command()

        handle_inc(ack=ack, body=body, command=command, respond=respond)

        ack.assert_called_once()
        respond.assert_called_once()
        response_text = respond.call_args[0][0]
        assert "Firetower Incident Bot" in response_text
        assert "/inc help" in response_text

    @patch("firetower.slack_app.bolt.statsd")
    def test_empty_text_returns_help(self, mock_statsd):
        ack = MagicMock()
        respond = MagicMock()
        body = self._make_body(text="")
        command = self._make_command()

        handle_inc(ack=ack, body=body, command=command, respond=respond)

        ack.assert_called_once()
        respond.assert_called_once()
        response_text = respond.call_args[0][0]
        assert "Firetower Incident Bot" in response_text

    @patch("firetower.slack_app.bolt.statsd")
    def test_unknown_subcommand_returns_error(self, mock_statsd):
        ack = MagicMock()
        respond = MagicMock()
        body = self._make_body(text="unknown")
        command = self._make_command()

        handle_inc(ack=ack, body=body, command=command, respond=respond)

        ack.assert_called_once()
        respond.assert_called_once()
        response_text = respond.call_args[0][0]
        assert "Unknown command" in response_text
        assert "/inc unknown" in response_text

    @patch("firetower.slack_app.bolt.statsd")
    def test_help_uses_testinc_command(self, mock_statsd):
        ack = MagicMock()
        respond = MagicMock()
        body = self._make_body(text="help", command="/testinc")
        command = self._make_command(command="/testinc")

        handle_inc(ack=ack, body=body, command=command, respond=respond)

        ack.assert_called_once()
        response_text = respond.call_args[0][0]
        assert "/testinc help" in response_text

    @patch("firetower.slack_app.bolt.statsd")
    def test_emits_submitted_and_completed_metrics(self, mock_statsd):
        ack = MagicMock()
        respond = MagicMock()
        body = self._make_body(text="help")
        command = self._make_command()

        handle_inc(ack=ack, body=body, command=command, respond=respond)

        mock_statsd.increment.assert_has_calls(
            [
                call("slack_app.commands.submitted", tags=["subcommand:help"]),
                call("slack_app.commands.completed", tags=["subcommand:help"]),
            ]
        )

    @patch("firetower.slack_app.bolt.statsd")
    def test_emits_failed_metric_on_error(self, mock_statsd):
        ack = MagicMock()
        respond = MagicMock(side_effect=RuntimeError("boom"))
        body = self._make_body(text="help")
        command = self._make_command()

        with pytest.raises(RuntimeError):
            handle_inc(ack=ack, body=body, command=command, respond=respond)

        mock_statsd.increment.assert_any_call(
            "slack_app.commands.submitted", tags=["subcommand:help"]
        )
        mock_statsd.increment.assert_any_call(
            "slack_app.commands.failed", tags=["subcommand:help"]
        )
