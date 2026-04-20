from unittest.mock import MagicMock, patch

import pytest
import requests

from firetower.integrations.services.pagerduty import PagerDutyService

MOCK_PD_CONFIG = {
    "API_TOKEN": "test-token",
    "ESCALATION_POLICIES": {
        "IMOC": {
            "id": "PIMOC01",
            "integration_key": "imoc-integration-key",
        },
        "PROD_ENG": {
            "id": "PPE001",
            "integration_key": "prod-eng-integration-key",
        },
    },
}


@pytest.fixture
def pd_service():
    with patch("firetower.integrations.services.pagerduty.settings") as mock_settings:
        mock_settings.PAGERDUTY = MOCK_PD_CONFIG
        return PagerDutyService()


class TestPagerDutyServiceInit:
    def test_init_raises_when_unconfigured(self):
        with patch(
            "firetower.integrations.services.pagerduty.settings"
        ) as mock_settings:
            mock_settings.PAGERDUTY = None
            with pytest.raises(ValueError, match="not configured"):
                PagerDutyService()

    def test_init_stores_config(self, pd_service):
        assert pd_service.api_token == "test-token"


class TestTriggerIncident:
    @patch("firetower.integrations.services.pagerduty.requests.post")
    def test_trigger_success(self, mock_post, pd_service):
        mock_post.return_value = MagicMock(status_code=202)

        result = pd_service.trigger_incident("Server down", "dedup-123", "int-key")

        assert result is True
        mock_post.assert_called_once()
        mock_post.return_value.raise_for_status.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["json"]["routing_key"] == "int-key"
        assert call_kwargs.kwargs["json"]["dedup_key"] == "dedup-123"
        assert call_kwargs.kwargs["json"]["payload"]["summary"] == "Server down"

    @patch("firetower.integrations.services.pagerduty.requests.post")
    def test_trigger_failure(self, mock_post, pd_service):
        mock_post.side_effect = requests.RequestException("connection error")

        result = pd_service.trigger_incident("Server down", "dedup-123", "int-key")

        assert result is False


class TestGetOncallUsers:
    @patch("firetower.integrations.services.pagerduty.requests.get")
    def test_returns_users_with_escalation_level(self, mock_get, pd_service):
        mock_get.return_value = MagicMock(
            json=lambda: {
                "oncalls": [
                    {
                        "user": {"email": "alice@example.com"},
                        "escalation_level": 1,
                    },
                    {
                        "user": {"email": "bob@example.com"},
                        "escalation_level": 2,
                    },
                ]
            }
        )

        users = pd_service.get_oncall_users("P17I207")

        assert users == [
            {"email": "alice@example.com", "escalation_level": 1},
            {"email": "bob@example.com", "escalation_level": 2},
        ]
        mock_get.assert_called_once()
        assert mock_get.call_args.kwargs["params"] == {
            "escalation_policy_ids[]": "P17I207",
            "limit": 100,
            "include[]": "users",
        }

    @patch("firetower.integrations.services.pagerduty.requests.get")
    def test_returns_empty_list_when_no_oncalls(self, mock_get, pd_service):
        mock_get.return_value = MagicMock(json=lambda: {"oncalls": []})

        users = pd_service.get_oncall_users("P17I207")

        assert users == []

    @patch("firetower.integrations.services.pagerduty.requests.get")
    def test_returns_empty_list_on_api_error(self, mock_get, pd_service):
        mock_get.side_effect = requests.RequestException("timeout")

        users = pd_service.get_oncall_users("P17I207")

        assert users == []

    @patch("firetower.integrations.services.pagerduty.requests.get")
    def test_skips_users_without_email(self, mock_get, pd_service):
        mock_get.return_value = MagicMock(
            json=lambda: {
                "oncalls": [
                    {"user": {}, "escalation_level": 1},
                    {"user": {"email": "alice@example.com"}, "escalation_level": 2},
                ]
            }
        )

        users = pd_service.get_oncall_users("P17I207")

        assert users == [{"email": "alice@example.com", "escalation_level": 2}]
