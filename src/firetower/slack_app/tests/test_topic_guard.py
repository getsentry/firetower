from unittest.mock import MagicMock, patch

import pytest

from firetower.slack_app.handlers import topic_guard
from firetower.slack_app.handlers.topic_guard import handle_channel_topic_change

CHANNEL_ID = "C_TEST_CHANNEL"
BOT_USER_ID = "U0000"
CANONICAL = "[P2] <https://ft/INC-1|INC-1 Test>"


@pytest.fixture(autouse=True)
def reset_module_state():
    topic_guard._bot_user_id = None
    topic_guard._recent_event_ids.clear()
    yield
    topic_guard._bot_user_id = None
    topic_guard._recent_event_ids.clear()


@pytest.fixture
def client():
    c = MagicMock()
    c.auth_test.return_value = {"user_id": BOT_USER_ID}
    return c


_TS_COUNTER = [0]


def _event(user="U_OTHER", topic="Something custom", channel=CHANNEL_ID, ts=None):
    if ts is None:
        _TS_COUNTER[0] += 1
        ts = f"1700000000.{_TS_COUNTER[0]:06d}"
    return {
        "type": "message",
        "subtype": "channel_topic",
        "channel": channel,
        "user": user,
        "topic": topic,
        "event_ts": ts,
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
@patch("firetower.slack_app.handlers.topic_guard.get_incident_from_channel")
def test_missing_channel_is_noop(mock_get_incident, mock_slack_service, client):
    event = _event()
    del event["channel"]

    handle_channel_topic_change(event, client)

    mock_get_incident.assert_not_called()
    mock_slack_service.set_channel_topic.assert_not_called()
    client.chat_postEphemeral.assert_not_called()


@patch("firetower.slack_app.handlers.topic_guard._slack_service")
@patch("firetower.slack_app.handlers.topic_guard.build_channel_topic")
@patch("firetower.slack_app.handlers.topic_guard.get_incident_from_channel")
def test_attempted_topic_is_escaped(
    mock_get_incident, mock_build_topic, mock_slack_service, client
):
    mock_get_incident.return_value = MagicMock()
    mock_build_topic.return_value = CANONICAL

    handle_channel_topic_change(
        _event(topic="<!channel> see <https://evil|here> & <@U999>"), client
    )

    text = client.chat_postEphemeral.call_args[1]["text"]
    assert "<!channel>" not in text
    assert "<@U999>" not in text
    assert "<https://evil|here>" not in text
    assert "&lt;!channel&gt;" in text
    assert "&amp;" in text


@patch("firetower.slack_app.handlers.topic_guard._slack_service")
@patch("firetower.slack_app.handlers.topic_guard.build_channel_topic")
@patch("firetower.slack_app.handlers.topic_guard.get_incident_from_channel")
def test_ephemeral_failure_still_resets(
    mock_get_incident, mock_build_topic, mock_slack_service, client
):
    mock_get_incident.return_value = MagicMock()
    mock_build_topic.return_value = CANONICAL
    client.chat_postEphemeral.side_effect = Exception("boom")

    handle_channel_topic_change(_event(), client)

    mock_slack_service.set_channel_topic.assert_called_once_with(CHANNEL_ID, CANONICAL)
    client.chat_postEphemeral.assert_called_once()


@patch("firetower.slack_app.handlers.topic_guard._slack_service")
@patch("firetower.slack_app.handlers.topic_guard.build_channel_topic")
@patch("firetower.slack_app.handlers.topic_guard.get_incident_from_channel")
def test_bot_id_cache_is_reused(
    mock_get_incident, mock_build_topic, mock_slack_service, client
):
    mock_get_incident.return_value = MagicMock()
    mock_build_topic.return_value = CANONICAL

    handle_channel_topic_change(_event(), client)
    handle_channel_topic_change(_event(), client)

    assert client.auth_test.call_count == 1


@patch("firetower.slack_app.handlers.topic_guard._slack_service")
@patch("firetower.slack_app.handlers.topic_guard.get_incident_from_channel")
def test_auth_test_failure_does_not_crash(
    mock_get_incident, mock_slack_service, client
):
    client.auth_test.side_effect = Exception("transient")

    handle_channel_topic_change(_event(), client)

    mock_get_incident.assert_called_once()


@patch("firetower.slack_app.handlers.topic_guard._slack_service")
@patch("firetower.slack_app.handlers.topic_guard.build_channel_topic")
@patch("firetower.slack_app.handlers.topic_guard.get_incident_from_channel")
def test_duplicate_event_id_is_skipped(
    mock_get_incident, mock_build_topic, mock_slack_service, client
):
    mock_get_incident.return_value = MagicMock()
    mock_build_topic.return_value = CANONICAL
    event = _event(ts="1700000000.999999")

    handle_channel_topic_change(event, client)
    handle_channel_topic_change(event, client)

    mock_slack_service.set_channel_topic.assert_called_once()
    client.chat_postEphemeral.assert_called_once()


@patch("firetower.slack_app.handlers.topic_guard._slack_service")
@patch("firetower.slack_app.handlers.topic_guard.build_channel_topic")
@patch("firetower.slack_app.handlers.topic_guard.get_incident_from_channel")
def test_slack_retry_header_is_skipped(
    mock_get_incident, mock_build_topic, mock_slack_service, client
):
    mock_get_incident.return_value = MagicMock()
    mock_build_topic.return_value = CANONICAL
    request = MagicMock()
    request.headers = {"x-slack-retry-num": ["1"]}

    handle_channel_topic_change(_event(), client, request=request)

    mock_slack_service.set_channel_topic.assert_not_called()
    client.chat_postEphemeral.assert_not_called()
