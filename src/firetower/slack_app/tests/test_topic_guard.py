from unittest.mock import MagicMock, patch

import pytest

from firetower.slack_app.handlers import topic_guard
from firetower.slack_app.handlers.topic_guard import handle_channel_topic_change

CHANNEL_ID = "C_TEST_CHANNEL"
BOT_USER_ID = "U0000"
CANONICAL = "[P2] <https://ft/INC-1|INC-1 Test>"


@pytest.fixture(autouse=True)
def reset_bot_user_cache():
    topic_guard._bot_user_id = None
    yield
    topic_guard._bot_user_id = None


@pytest.fixture
def client():
    c = MagicMock()
    c.auth_test.return_value = {"user_id": BOT_USER_ID}
    return c


def _event(user="U_OTHER", topic="Something custom", channel=CHANNEL_ID):
    return {
        "type": "message",
        "subtype": "channel_topic",
        "channel": channel,
        "user": user,
        "topic": topic,
    }


@patch("firetower.slack_app.handlers.topic_guard._slack_service")
@patch("firetower.slack_app.handlers.topic_guard.build_channel_topic")
@patch("firetower.slack_app.handlers.topic_guard.get_incident_from_channel")
def test_manual_change_resets_and_notifies(
    mock_get_incident, mock_build_topic, mock_slack_service, client
):
    mock_get_incident.return_value = MagicMock()
    mock_build_topic.return_value = CANONICAL

    handle_channel_topic_change(_event(topic="My custom topic"), client)

    mock_slack_service.set_channel_topic.assert_called_once_with(CHANNEL_ID, CANONICAL)
    client.chat_postEphemeral.assert_called_once()
    kwargs = client.chat_postEphemeral.call_args[1]
    assert kwargs["channel"] == CHANNEL_ID
    assert kwargs["user"] == "U_OTHER"
    assert "My custom topic" in kwargs["text"]


@patch("firetower.slack_app.handlers.topic_guard._slack_service")
@patch("firetower.slack_app.handlers.topic_guard.get_incident_from_channel")
def test_bot_authored_event_is_ignored(mock_get_incident, mock_slack_service, client):
    handle_channel_topic_change(_event(user=BOT_USER_ID), client)

    mock_get_incident.assert_not_called()
    mock_slack_service.set_channel_topic.assert_not_called()
    client.chat_postEphemeral.assert_not_called()


@patch("firetower.slack_app.handlers.topic_guard._slack_service")
@patch("firetower.slack_app.handlers.topic_guard.get_incident_from_channel")
def test_non_incident_channel_is_noop(mock_get_incident, mock_slack_service, client):
    mock_get_incident.return_value = None

    handle_channel_topic_change(_event(), client)

    mock_slack_service.set_channel_topic.assert_not_called()
    client.chat_postEphemeral.assert_not_called()


@patch("firetower.slack_app.handlers.topic_guard._slack_service")
@patch("firetower.slack_app.handlers.topic_guard.build_channel_topic")
@patch("firetower.slack_app.handlers.topic_guard.get_incident_from_channel")
def test_topic_already_canonical_is_noop(
    mock_get_incident, mock_build_topic, mock_slack_service, client
):
    mock_get_incident.return_value = MagicMock()
    mock_build_topic.return_value = CANONICAL

    handle_channel_topic_change(_event(topic=CANONICAL), client)

    mock_slack_service.set_channel_topic.assert_not_called()
    client.chat_postEphemeral.assert_not_called()
