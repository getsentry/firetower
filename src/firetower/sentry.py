import logging

from sentry_sdk.types import Event, Hint

_SLACK_RECONNECT_LOG_PREFIXES = (
    "Failed to retrieve WSS URL: ",
    "Failed to check the current session or reconnect to the server (",
)


def before_send(event: Event, hint: Hint) -> Event | None:
    """Keep handled Slack reconnect failures as logs, not issues."""
    if (
        event.get("logger") != "slack_bolt.App"
        or event.get("level") != "error"
        or event.get("exception")
    ):
        return event

    record = hint.get("log_record")
    if isinstance(record, logging.LogRecord) and record.getMessage().startswith(
        _SLACK_RECONNECT_LOG_PREFIXES
    ):
        return None

    return event
