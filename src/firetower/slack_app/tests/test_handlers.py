from unittest.mock import MagicMock

from firetower.slack_app.bolt import handle_inc


class TestHandleInc:
    def _make_body(self, text="", command="/inc"):
        return {"text": text, "command": command}

    def _make_command(self, command="/inc", text=""):
        return {"command": command, "text": text}

    def test_help_returns_help_text(self):
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

    def test_empty_text_returns_help(self):
        ack = MagicMock()
        respond = MagicMock()
        body = self._make_body(text="")
        command = self._make_command()

        handle_inc(ack=ack, body=body, command=command, respond=respond)

        ack.assert_called_once()
        respond.assert_called_once()
        response_text = respond.call_args[0][0]
        assert "Firetower Incident Bot" in response_text

    def test_unknown_subcommand_returns_error(self):
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

    def test_help_uses_testinc_command(self):
        ack = MagicMock()
        respond = MagicMock()
        body = self._make_body(text="help", command="/testinc")
        command = self._make_command(command="/testinc")

        handle_inc(ack=ack, body=body, command=command, respond=respond)

        ack.assert_called_once()
        response_text = respond.call_args[0][0]
        assert "/testinc help" in response_text
