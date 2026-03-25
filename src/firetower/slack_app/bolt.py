import logging
from typing import Any

from datadog import statsd
from django.conf import settings
from slack_bolt import App

from firetower.slack_app.handlers.help import handle_help_command

logger = logging.getLogger(__name__)

METRICS_PREFIX = "slack_app.commands"

_bolt_app: App | None = None


def get_bolt_app() -> App:
    """Lazy-init to avoid an auth_test API call at import time."""
    global _bolt_app  # noqa: PLW0603
    if _bolt_app is None:
        _bolt_app = App(token=settings.SLACK["BOT_TOKEN"])
        _bolt_app.command("/ft")(handle_command)
        _bolt_app.command("/ft-test")(handle_command)
    return _bolt_app


def handle_command(ack: Any, body: dict, command: dict, respond: Any) -> None:
    subcommand = (body.get("text") or "").strip().lower()
    metric_subcommand = "help" if subcommand in ("", "help") else "unknown"
    tags = [f"subcommand:{metric_subcommand}"]
    statsd.increment(f"{METRICS_PREFIX}.submitted", tags=tags)

    try:
        if subcommand in ("help", ""):
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
