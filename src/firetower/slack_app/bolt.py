import logging
from typing import Any

from django.conf import settings
from slack_bolt import App

from firetower.slack_app.handlers.help import handle_help_command

logger = logging.getLogger(__name__)

slack_config = settings.SLACK

bolt_app = App(
    token=slack_config["BOT_TOKEN"],
    signing_secret=slack_config["SIGNING_SECRET"],
    token_verification_enabled=False,
)


@bolt_app.command("/inc")
@bolt_app.command("/testinc")
def handle_inc(ack: Any, body: dict, command: dict, respond: Any) -> None:
    subcommand = (body.get("text") or "").strip().lower()

    if subcommand in ("help", ""):
        handle_help_command(ack, command, respond)
    else:
        ack()
        cmd = command.get("command", "/inc")
        respond(f"Unknown command: `{cmd} {subcommand}`. Try `{cmd} help`.")
