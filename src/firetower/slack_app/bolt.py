import logging
from typing import Any

from datadog import statsd
from django.conf import settings
from slack_bolt import App

from firetower.slack_app.handlers.help import handle_help_command

logger = logging.getLogger(__name__)

METRICS_PREFIX = "slack_app.commands"

slack_config = settings.SLACK

bolt_app = App(token=slack_config["BOT_TOKEN"])


@bolt_app.command("/inc")
@bolt_app.command("/testinc")
def handle_inc(ack: Any, body: dict, command: dict, respond: Any) -> None:
    subcommand = (body.get("text") or "").strip().lower()
    tags = [f"subcommand:{subcommand or 'help'}"]
    statsd.increment(f"{METRICS_PREFIX}.submitted", tags=tags)

    try:
        if subcommand in ("help", ""):
            handle_help_command(ack, command, respond)
        else:
            ack()
            cmd = command.get("command", "/inc")
            respond(f"Unknown command: `{cmd} {subcommand}`. Try `{cmd} help`.")
        statsd.increment(f"{METRICS_PREFIX}.completed", tags=tags)
    except Exception:
        logger.exception(
            "Slash command failed: %s %s", command.get("command", "/inc"), subcommand
        )
        statsd.increment(f"{METRICS_PREFIX}.failed", tags=tags)
        raise
