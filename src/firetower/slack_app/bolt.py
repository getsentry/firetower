import logging
from typing import Any

from datadog import statsd
from django.conf import settings
from slack_bolt import App

from firetower.slack_app.handlers.help import handle_help_command
from firetower.slack_app.handlers.mitigated import (
    handle_mitigated_command,
    handle_mitigated_submission,
)
from firetower.slack_app.handlers.new_incident import (
    handle_new_command,
    handle_new_incident_submission,
)
from firetower.slack_app.handlers.reopen import handle_reopen_command
from firetower.slack_app.handlers.resolved import (
    handle_resolved_command,
    handle_resolved_submission,
)
from firetower.slack_app.handlers.severity import handle_severity_command
from firetower.slack_app.handlers.subject import handle_subject_command

logger = logging.getLogger(__name__)

METRICS_PREFIX = "slack_app.commands"

KNOWN_SUBCOMMANDS = {
    "help",
    "new",
    "mitigated",
    "mit",
    "resolved",
    "fixed",
    "reopen",
    "severity",
    "sev",
    "setseverity",
    "subject",
}

slack_config = settings.SLACK

bolt_app = App(token=slack_config["BOT_TOKEN"])


@bolt_app.command("/ft")
@bolt_app.command("/ft-test")
def handle_inc(ack: Any, body: dict, command: dict, respond: Any) -> None:
    raw_text = (body.get("text") or "").strip()
    parts = raw_text.split(None, 1)
    subcommand = parts[0].lower() if parts else ""
    args = parts[1] if len(parts) > 1 else ""

    metric_subcommand = (
        (subcommand or "help")
        if subcommand in KNOWN_SUBCOMMANDS or subcommand == ""
        else "unknown"
    )
    tags = [f"subcommand:{metric_subcommand}"]
    statsd.increment(f"{METRICS_PREFIX}.submitted", tags=tags)

    try:
        if subcommand == "new":
            handle_new_command(ack, body, command, respond)
        elif subcommand in ("help", ""):
            handle_help_command(ack, command, respond)
        elif subcommand in ("mitigated", "mit"):
            handle_mitigated_command(ack, body, command, respond)
        elif subcommand in ("resolved", "fixed"):
            handle_resolved_command(ack, body, command, respond)
        elif subcommand == "reopen":
            handle_reopen_command(ack, body, command, respond)
        elif subcommand in ("severity", "sev", "setseverity"):
            if not args:
                ack()
                cmd = command.get("command", "/ft")
                respond(f"Usage: `{cmd} severity <P0-P4>`")
            else:
                handle_severity_command(ack, body, command, respond, new_severity=args)
        elif subcommand == "subject":
            if not args:
                ack()
                cmd = command.get("command", "/ft")
                respond(f"Usage: `{cmd} subject <new title>`")
            else:
                handle_subject_command(ack, body, command, respond, new_subject=args)
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
bolt_app.view("mitigated_incident_modal")(handle_mitigated_submission)
bolt_app.view("resolved_incident_modal")(handle_resolved_submission)
