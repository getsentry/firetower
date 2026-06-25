import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from datadog import statsd
from django.conf import settings
from django.db import close_old_connections
from slack_bolt import App

from firetower.slack_app.handlers.backfill_incident import (
    handle_backfill_command,
    handle_backfill_submission,
)
from firetower.slack_app.handlers.cancel import (
    handle_cancel_command,
    handle_cancel_submission,
)
from firetower.slack_app.handlers.captain import (
    handle_captain_command,
    handle_captain_submission,
)
from firetower.slack_app.handlers.dumpslack import handle_dumpslack_command
from firetower.slack_app.handlers.help import handle_help_command
from firetower.slack_app.handlers.list_incidents import handle_list_command
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
from firetower.slack_app.handlers.status import handle_status_command
from firetower.slack_app.handlers.statuspage import (
    handle_component_impact_select,
    handle_statuspage_command,
    handle_statuspage_reset_and_resolve,
    handle_statuspage_resolve_anyway,
    handle_statuspage_submission,
)
from firetower.slack_app.handlers.subject import handle_subject_command
from firetower.slack_app.handlers.topic_guard import handle_channel_topic_change
from firetower.slack_app.handlers.update_incident import (
    handle_update_command,
    handle_update_incident_submission,
)

logger = logging.getLogger(__name__)

METRICS_PREFIX = "slack_app.commands"

KNOWN_SUBCOMMANDS = {
    "help",
    "new",
    "backfill",
    "mitigated",
    "mit",
    "resolved",
    "fixed",
    "reopen",
    "cancel",
    "list",
    "ls",
    "severity",
    "sev",
    "setseverity",
    "subject",
    "title",
    "update",
    "edit",
    "captain",
    "ic",
    "status",
    "statuspage",
    "dumpslack",
}

_bolt_app: App | None = None


def _db_connection_middleware(next: Any) -> None:
    """Close stale Django DB connections before each Slack handler.

    In a long-running Socket Mode process Django's request middleware never
    runs, so connections can become stale/broken after the PostgreSQL server
    drops idle SSL sessions.  Calling close_old_connections() here mirrors
    what Django's BaseHandler does on request_started.
    """
    close_old_connections()
    next()


def get_bolt_app() -> App:
    """Lazy-init to avoid an auth_test API call at import time."""
    global _bolt_app  # noqa: PLW0603
    if _bolt_app is None:
        _bolt_app = App(token=settings.SLACK["BOT_TOKEN"])
        _bolt_app.use(_db_connection_middleware)
        _bolt_app.command("/ft")(handle_command)
        _bolt_app.command("/ft-test")(handle_command)
        _bolt_app.command("/inc")(handle_command)
        _bolt_app.command("/testinc")(handle_command)
        _register_views(_bolt_app)
        _register_event_handlers(_bolt_app)
    return _bolt_app


def handle_command(
    ack: Any, body: dict, command: dict, respond: Any, client: Any = None
) -> None:
    close_old_connections()
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
        elif subcommand == "backfill":
            handle_backfill_command(ack, body, command, respond)
        elif subcommand in ("help", ""):
            handle_help_command(ack, command, respond)
        elif subcommand in ("mitigated", "mit"):
            handle_mitigated_command(ack, body, command, respond)
        elif subcommand in ("resolved", "fixed"):
            handle_resolved_command(ack, body, command, respond)
        elif subcommand == "reopen":
            handle_reopen_command(ack, body, command, respond)
        elif subcommand == "cancel":
            handle_cancel_command(ack, body, command, respond)
        elif subcommand in ("list", "ls"):
            handle_list_command(ack, body, command, respond, client=client)
        elif subcommand in ("severity", "sev", "setseverity"):
            if not args:
                ack()
                cmd = command.get("command", "/ft")
                respond(f"Usage: `{cmd} severity <P0-P4>`")
            else:
                handle_severity_command(ack, body, command, respond, new_severity=args)
        elif subcommand in ("update", "edit"):
            handle_update_command(ack, body, command, respond)
        elif subcommand in ("subject", "title"):
            if not args:
                ack()
                cmd = command.get("command", "/ft")
                respond(f"Usage: `{cmd} subject <new title>`")
            else:
                handle_subject_command(ack, body, command, respond, new_subject=args)
        elif subcommand in ("captain", "ic"):
            handle_captain_command(ack, body, command, respond)
        elif subcommand == "status":
            handle_status_command(ack, body, command, respond)
        elif subcommand == "statuspage":
            handle_statuspage_command(ack, body, command, respond)
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


def _with_metrics(callback_id: str) -> Callable[..., Callable[..., Any]]:
    """Wrap a Bolt handler to emit submitted/completed/failed metrics."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            close_old_connections()
            tags = [f"callback_id:{callback_id}"]
            statsd.increment("slack_app.views.submitted", tags=tags)
            try:
                result = func(*args, **kwargs)
                statsd.increment("slack_app.views.completed", tags=tags)
                return result
            except Exception:
                logger.exception("View handler failed: %s", callback_id)
                statsd.increment("slack_app.views.failed", tags=tags)
                raise

        return wrapper

    return decorator


def _register_views(app: App) -> None:
    """Register view handlers (modals, etc.) on the Bolt app."""
    app.view("backfill_incident_modal")(
        _with_metrics("backfill_incident_modal")(handle_backfill_submission)
    )
    app.view("new_incident_modal")(
        _with_metrics("new_incident_modal")(handle_new_incident_submission)
    )
    app.view("update_incident_modal")(
        _with_metrics("update_incident_modal")(handle_update_incident_submission)
    )
    app.view("mitigated_incident_modal")(
        _with_metrics("mitigated_incident_modal")(handle_mitigated_submission)
    )
    app.view("cancel_incident_modal")(
        _with_metrics("cancel_incident_modal")(handle_cancel_submission)
    )
    app.view("resolved_incident_modal")(
        _with_metrics("resolved_incident_modal")(handle_resolved_submission)
    )
    app.view("captain_incident_modal")(
        _with_metrics("captain_incident_modal")(handle_captain_submission)
    )
    app.view("statuspage_modal")(
        _with_metrics("statuspage_modal")(handle_statuspage_submission)
    )
    app.action("component_impact_select")(
        _with_metrics("component_impact_select")(handle_component_impact_select)
    )
    app.action("statuspage_reset_and_resolve")(
        _with_metrics("statuspage_reset_and_resolve")(
            handle_statuspage_reset_and_resolve
        )
    )
    app.action("statuspage_resolve_anyway")(
        _with_metrics("statuspage_resolve_anyway")(handle_statuspage_resolve_anyway)
    )
    for action_id in (
        "impact_type_tags",
        "affected_service_tags",
        "affected_region_tags",
    ):
        app.options(action_id)(handle_tag_options)


def _register_event_handlers(app: App) -> None:
    """Register Slack event subscriptions on the Bolt app."""
    app.event({"type": "message", "subtype": "channel_topic"})(
        _with_metrics("channel_topic")(handle_channel_topic_change)
    )
