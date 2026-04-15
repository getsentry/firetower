from unittest.mock import MagicMock

from firetower.slack_app.handlers.dumpslack import handle_dumpslack_command


class TestDumpslackCommand:
    def test_returns_not_implemented(self):
        ack = MagicMock()
        respond = MagicMock()
        command = {"command": "/ft"}

        handle_dumpslack_command(ack, command, respond)

        ack.assert_called_once()
        respond.assert_called_once()
        assert "not yet implemented" in respond.call_args[0][0]
