import logging
from typing import Any

from datadog import statsd
from django.conf import settings
from slack_bolt import App

from firetower.slack_app.handlers.help import handle_help_command
from firetower.slack_app.handlers.new_incident import (
    handle_new_command,
    handle_new_incident_submission,
)

logger = logging.getLogger(__name__)

METRICS_PREFIX = "slack_app.commands"

slack_config = settings.SLACK

bolt_app = App(token=slack_config["BOT_TOKEN"])


@bolt_app.command("/ft")
@bolt_app.command("/ft-test")
def handle_inc(ack: Any, body: dict, command: dict, respond: Any) -> None:
    subcommand = (body.get("text") or "").strip().lower()
    metric_subcommand = (
        (subcommand or "help") if subcommand in ("", "help", "new") else "unknown"
    )
    tags = [f"subcommand:{metric_subcommand}"]
    statsd.increment(f"{METRICS_PREFIX}.submitted", tags=tags)

    try:
        if subcommand == "new":
            handle_new_command(ack, body, command, respond)
        elif subcommand in ("help", ""):
            handle_help_command(ack, command, respond)
        else:
            ack()
            cmd = command.get("command", "/ft")
            respond(f"Unknown command: `{cmd} {subcommand}`. Try `{cmd} help`.")
        statsd.increment(f"{METRICS_PREFIX}.completed", tags=tags)
    except Exception:
        logger.exception(
            "Slash command failed: %s %s", command.get("command", "/ft"), subcommand
        )
        statsd.increment(f"{METRICS_PREFIX}.failed", tags=tags)
        raise


bolt_app.view("new_incident_modal")(handle_new_incident_submission)
