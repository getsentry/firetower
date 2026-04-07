from unittest.mock import patch

import pytest
from slack_sdk.web import WebClient


@pytest.fixture(autouse=True)
def mock_slack_auth():
    with patch.object(
        WebClient,
        "auth_test",
        return_value={
            "ok": True,
            "user_id": "U0000",
            "team_id": "T0000",
            "bot_id": "B0000",
        },
    ):
        yield
