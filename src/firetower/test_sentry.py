import json
import logging

import pytest
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.transport import Transport

from firetower.sentry import before_send

_RECONNECT_MESSAGES = (
    "Failed to retrieve WSS URL: The request to the Slack API failed. "
    "The server responded with: {'ok': False, 'error': 'invalid_auth'}",
    "Failed to check the current session or reconnect to the server "
    "(session id: test-session, error: SlackApiError, message: invalid_auth)",
)


def _log_record(message, logger="slack_bolt.App", level=logging.ERROR):
    return logging.LogRecord(logger, level, __file__, 1, message, (), None)


@pytest.mark.parametrize("message", _RECONNECT_MESSAGES)
def test_before_send_drops_handled_slack_reconnect_logs(message):
    event = {"logger": "slack_bolt.App", "level": "error"}

    assert before_send(event, {"log_record": _log_record(message)}) is None


@pytest.mark.parametrize("message", _RECONNECT_MESSAGES)
def test_before_send_preserves_exception_events(message):
    event = {
        "logger": "slack_bolt.App",
        "level": "error",
        "exception": {"values": [{"type": "RuntimeError", "value": "unexpected"}]},
    }

    assert before_send(event, {"log_record": _log_record(message)}) is event


@pytest.mark.parametrize("message", _RECONNECT_MESSAGES)
@pytest.mark.parametrize(
    ("logger", "level"),
    [("firetower.slack_app", "error"), ("slack_bolt.App", "fatal")],
)
def test_before_send_preserves_other_loggers_and_levels(message, logger, level):
    event = {"logger": logger, "level": level}

    assert before_send(event, {"log_record": _log_record(message, logger)}) is event


@pytest.mark.parametrize(
    "event",
    [
        {},
        {"logger": "slack_bolt.App", "level": "error"},
        {"logger": "slack_bolt.App", "level": "error", "logentry": None},
    ],
)
def test_before_send_preserves_events_without_log_record(event):
    assert before_send(event, {}) is event


@pytest.mark.parametrize(
    "message",
    [
        "Unexpected handler failure",
        "Slack bot crashed: invalid_auth, restarting in 5s",
        "Slack WebSocket error: unexpected failure",
    ],
)
def test_before_send_preserves_other_errors(message):
    event = {"logger": "slack_bolt.App", "level": "error"}

    assert before_send(event, {"log_record": _log_record(message)}) is event


class _MemoryTransport(Transport):
    def __init__(self):
        super().__init__()
        self.envelopes = []

    def capture_envelope(self, envelope):
        self.envelopes.append(envelope)


def test_reconnect_filter_preserves_logs_breadcrumbs_and_unrelated_issues(caplog):
    transport = _MemoryTransport()
    logger = logging.getLogger("slack_bolt.App")
    unexpected_message = "Unexpected handler failure"

    with (
        sentry_sdk.Client(
            dsn="https://public@example.invalid/1",
            default_integrations=False,
            integrations=[LoggingIntegration()],
            transport=transport,
            before_send=before_send,
            enable_logs=True,
        ) as client,
        sentry_sdk.isolation_scope() as scope,
    ):
        scope.set_client(client)
        for message in _RECONNECT_MESSAGES:
            logger.error(message)
        logger.error(unexpected_message)
        client.flush()

    events = [
        event
        for envelope in transport.envelopes
        if (event := envelope.get_event()) is not None
    ]
    assert len(events) == 1
    assert events[0]["logentry"]["formatted"] == unexpected_message
    breadcrumb_messages = {
        crumb["message"] for crumb in events[0]["breadcrumbs"]["values"]
    }
    assert set(_RECONNECT_MESSAGES) <= breadcrumb_messages

    log_messages = {
        log["body"]
        for envelope in transport.envelopes
        for item in envelope.items
        if item.headers["type"] == "log"
        for log in json.loads(item.get_bytes())["items"]
    }
    assert set(_RECONNECT_MESSAGES) <= log_messages
    assert set(_RECONNECT_MESSAGES) <= set(caplog.messages)
