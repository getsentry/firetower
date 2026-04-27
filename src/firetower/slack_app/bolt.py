import logging
from typing import Any

from datadog import statsd
from django.conf import settings
from slack_bolt import App

from firetower.slack_app.handlers.captain import (
    handle_captain_command,
    handle_captain_submission,
)
from firetower.slack_app.handlers.dumpslack import handle_dumpslack_command
from firetower.slack_app.handlers.help import handle_help_command
from firetower.slack_app.handlers.mitigated import (
    handle_mitigated_command,
    handle_mitigated_submission,
)
from firetower.slack_app.handlers.new_incident import (
    handle_new_command,
    handle_new_incident_submission,
    handle_tag_options,
)
from firetower.slack_app.handlers.reopen import handle_reopen_command
from firetower.slack_app.handlers.resolved import (
    handle_resolved_command,
    handle_resolved_submission,
)
from firetower.slack_app.handlers.severity import handle_severity_command
from firetower.slack_app.handlers.statuspage import handle_statuspage_command
from firetower.slack_app.handlers.subject import handle_subject_command
from firetower.slack_app.handlers.update_incident import (
    handle_update_command,
    handle_update_incident_submission,
)

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
    "update",
    "edit",
    "captain",
    "ic",
    "statuspage",
    "dumpslack",
}

_bolt_app: App | None = None


def get_bolt_app() -> App:
    """Lazy-init to avoid an auth_test API call at import time."""
    global _bolt_app  # noqa: PLW0603
    if _bolt_app is None:
        _bolt_app = App(token=settings.SLACK["BOT_TOKEN"])
        _bolt_app.command("/ft")(handle_command)
        _bolt_app.command("/ft-test")(handle_command)
        _register_views(_bolt_app)
    return _bolt_app


def handle_command(
    ack: Any, body: dict, command: dict, respond: Any, client: Any = None
) -> None:
    raw_text = (body.get("text") or "").strip()
    parts = raw_text.split(None, 1)
    subcommand = parts[0].lower() if parts else ""
    args = parts[1] if len(parts) > 1 else ""

    logger.debug(
        "Command triggered: %s %s (user=%s, channel=%s)",
        command.get("command", "/ft"),
        subcommand or "(none)",
        body.get("user_id", "unknown"),
        body.get("channel_id", "unknown"),
    )

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
        elif subcommand in ("update", "edit"):
            handle_update_command(ack, body, command, respond)
        elif subcommand == "subject":
            if not args:
                ack()
                cmd = command.get("command", "/ft")
                respond(f"Usage: `{cmd} subject <new title>`")
            else:
                handle_subject_command(ack, body, command, respond, new_subject=args)
        elif subcommand in ("captain", "ic"):
            handle_captain_command(ack, body, command, respond)
        elif subcommand == "statuspage":
            handle_statuspage_command(ack, command, respond)
        elif subcommand == "dumpslack":
            handle_dumpslack_command(ack, body, command, client, respond)
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


def _register_views(app: App) -> None:
    """Register view handlers (modals, etc.) on the Bolt app."""
    app.view("new_incident_modal")(handle_new_incident_submission)
    app.view("update_incident_modal")(handle_update_incident_submission)
    app.view("mitigated_incident_modal")(handle_mitigated_submission)
    app.view("resolved_incident_modal")(handle_resolved_submission)
    app.view("captain_incident_modal")(handle_captain_submission)
    for action_id in (
        "impact_type_tags",
        "affected_service_tags",
        "affected_region_tags",
    ):
        app.options(action_id)(handle_tag_options)
