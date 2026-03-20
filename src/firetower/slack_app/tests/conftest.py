from unittest.mock import patch

from slack_sdk.web import WebClient

mock_auth = patch.object(
    WebClient,
    "auth_test",
    return_value={
        "ok": True,
        "user_id": "U0000",
        "team_id": "T0000",
        "bot_id": "B0000",
    },
)
mock_auth.start()


def pytest_sessionfinish(session, exitstatus):
    mock_auth.stop()
