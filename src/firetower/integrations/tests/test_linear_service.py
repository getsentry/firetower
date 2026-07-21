from datetime import timedelta
from unittest.mock import MagicMock, call, patch

import pytest
import requests
from django.utils import timezone

from firetower.integrations.services.linear import (
    LINEAR_DEFAULT_MAX_RETRIES,
    LINEAR_DEFAULT_RETRY_BACKOFF_SECONDS,
    LINEAR_DEFAULT_TIMEOUT_SECONDS,
    LINEAR_TOKEN_URL,
    LinearError,
    LinearService,
    _errors_are_not_found,
    _summarize_graphql_errors,
    parse_project_number,
)


@pytest.fixture
def linear_service():
    with patch("firetower.integrations.services.linear.settings") as mock_settings:
        mock_settings.LINEAR = {
            "CLIENT_ID": "test-client-id",
            "CLIENT_SECRET": "test-client-secret",
        }
        svc = LinearService()
    return svc


@pytest.fixture
def mock_token():
    token = MagicMock()
    token.access_token = "valid-token"
    token.expires_at = timezone.now() + timedelta(days=15)
    return token


class TestGetAccessToken:
    def test_returns_none_when_no_credentials(self):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {"CLIENT_ID": "", "CLIENT_SECRET": ""}
            svc = LinearService()

        assert svc._get_access_token() is None

    @patch("firetower.integrations.services.linear.LinearOAuthToken")
    def test_returns_cached_token_when_valid(
        self, mock_token_model, linear_service, mock_token
    ):
        mock_token_model.get_singleton.return_value = mock_token

        result = linear_service._get_access_token()

        assert result == "valid-token"

    @patch("firetower.integrations.services.linear.LinearOAuthToken")
    def test_refreshes_when_token_expired(self, mock_token_model, linear_service):
        expired_token = MagicMock()
        expired_token.access_token = "expired-token"
        expired_token.expires_at = timezone.now() - timedelta(hours=1)
        mock_token_model.get_singleton.return_value = expired_token

        with patch.object(
            linear_service, "_request_new_token", return_value="new-token"
        ) as mock_refresh:
            result = linear_service._get_access_token()

        assert result == "new-token"
        mock_refresh.assert_called_once()

    @patch("firetower.integrations.services.linear.LinearOAuthToken")
    def test_refreshes_when_no_existing_token(self, mock_token_model, linear_service):
        mock_token_model.get_singleton.return_value = None

        with patch.object(
            linear_service, "_request_new_token", return_value="new-token"
        ):
            result = linear_service._get_access_token()

        assert result == "new-token"


class TestRequestNewToken:
    @patch("firetower.integrations.services.linear.LinearOAuthToken")
    @patch("firetower.integrations.services.linear.requests.post")
    def test_stores_token_and_returns_access_token(
        self, mock_post, mock_token_model, linear_service
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_response

        result = linear_service._request_new_token()

        assert result == "new-access-token"
        mock_post.assert_called_once_with(
            LINEAR_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",
                "scope": "read,write",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        mock_token_model.objects.all().delete.assert_called_once()
        mock_token_model.objects.create.assert_called_once()

    @patch("firetower.integrations.services.linear.requests.post")
    def test_returns_none_on_request_error(self, mock_post, linear_service):
        mock_post.side_effect = requests.RequestException("connection error")

        assert linear_service._request_new_token() is None


class TestGraphql:
    def test_returns_data_on_success(self, linear_service):
        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(linear_service, "_make_graphql_request") as mock_request,
        ):
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"viewer": {"id": "u1"}}}
            mock_request.return_value = mock_response

            result = linear_service._graphql("query { viewer { id } }")

        assert result == {"viewer": {"id": "u1"}}

    def test_returns_none_when_no_access_token(self, linear_service):
        with patch.object(linear_service, "_get_access_token", return_value=None):
            assert linear_service._graphql("query { viewer { id } }") is None

    def test_retries_on_401(self, linear_service):
        first_response = MagicMock()
        first_response.status_code = 401
        first_response.ok = False

        second_response = MagicMock()
        second_response.status_code = 200
        second_response.ok = True
        second_response.json.return_value = {"data": {"viewer": {"id": "u1"}}}

        with (
            patch.object(linear_service, "_get_access_token", return_value="old-token"),
            patch.object(
                linear_service,
                "_request_new_token",
                return_value="refreshed-token",
            ) as mock_refresh,
            patch.object(
                linear_service,
                "_make_graphql_request",
                side_effect=[first_response, second_response],
            ) as mock_request,
        ):
            result = linear_service._graphql("query { viewer { id } }")

        assert result == {"viewer": {"id": "u1"}}
        mock_refresh.assert_called_once()
        assert mock_request.call_count == 2
        assert mock_request.call_args_list[1] == call(
            "query { viewer { id } }", None, "refreshed-token"
        )

    def test_does_not_refresh_on_401_when_api_key_is_set(self, linear_service):
        linear_service.api_key = "lin_api_test"
        first_response = MagicMock()
        first_response.status_code = 401
        first_response.ok = False

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="lin_api_test"
            ),
            patch.object(linear_service, "_request_new_token") as mock_refresh,
            patch.object(
                linear_service, "_make_graphql_request", return_value=first_response
            ) as mock_request,
        ):
            assert linear_service._graphql("query { viewer { id } }") is None

        mock_refresh.assert_not_called()
        assert mock_request.call_count == 1

    def test_returns_none_when_401_and_refresh_fails(self, linear_service):
        first_response = MagicMock()
        first_response.status_code = 401
        first_response.ok = False

        with (
            patch.object(linear_service, "_get_access_token", return_value="old-token"),
            patch.object(linear_service, "_request_new_token", return_value=None),
            patch.object(
                linear_service, "_make_graphql_request", return_value=first_response
            ),
        ):
            assert linear_service._graphql("query { viewer { id } }") is None

    def test_returns_none_on_graphql_errors(self, linear_service):
        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(linear_service, "_make_graphql_request") as mock_request,
        ):
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "errors": [{"message": "some error"}],
                "data": None,
            }
            mock_request.return_value = mock_response

            assert linear_service._graphql("query { viewer { id } }") is None

    @pytest.mark.parametrize("status_code", [502, 503, 504])
    def test_retries_on_retryable_status_codes(self, linear_service, status_code):
        transient_response = MagicMock()
        transient_response.status_code = status_code
        transient_response.ok = False

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.ok = True
        success_response.json.return_value = {"data": {"viewer": {"id": "u1"}}}

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service,
                "_make_graphql_request",
                side_effect=[transient_response, success_response],
            ) as mock_request,
            patch.object(linear_service, "_sleep_before_retry") as mock_sleep,
        ):
            result = linear_service._graphql("query { viewer { id } }")

        assert result == {"viewer": {"id": "u1"}}
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once_with(0)

    def test_returns_none_after_exhausting_retries_on_retryable_status(
        self, linear_service
    ):
        transient_response = MagicMock()
        transient_response.status_code = 502
        transient_response.ok = False
        transient_response.text = "Bad Gateway"

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service,
                "_make_graphql_request",
                return_value=transient_response,
            ) as mock_request,
            patch.object(linear_service, "_sleep_before_retry") as mock_sleep,
        ):
            result = linear_service._graphql("query { viewer { id } }")

        assert result is None
        assert mock_request.call_count == LINEAR_DEFAULT_MAX_RETRIES
        assert mock_sleep.call_count == LINEAR_DEFAULT_MAX_RETRIES - 1

    def test_retries_on_request_exception(self, linear_service):
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.ok = True
        success_response.json.return_value = {"data": {"viewer": {"id": "u1"}}}

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service,
                "_make_graphql_request",
                side_effect=[
                    requests.ConnectionError("connection reset"),
                    success_response,
                ],
            ) as mock_request,
            patch.object(linear_service, "_sleep_before_retry") as mock_sleep,
        ):
            result = linear_service._graphql("query { viewer { id } }")

        assert result == {"viewer": {"id": "u1"}}
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once_with(0)

    def test_returns_none_after_exhausting_retries_on_request_exception(
        self, linear_service
    ):
        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service,
                "_make_graphql_request",
                side_effect=requests.ConnectionError("connection reset"),
            ) as mock_request,
            patch.object(linear_service, "_sleep_before_retry") as mock_sleep,
        ):
            result = linear_service._graphql("query { viewer { id } }")

        assert result is None
        assert mock_request.call_count == LINEAR_DEFAULT_MAX_RETRIES
        assert mock_sleep.call_count == LINEAR_DEFAULT_MAX_RETRIES - 1

    def test_no_retry_when_retryable_is_false(self, linear_service):
        transient_response = MagicMock()
        transient_response.status_code = 502
        transient_response.ok = False
        transient_response.text = "Bad Gateway"

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service,
                "_make_graphql_request",
                return_value=transient_response,
            ) as mock_request,
            patch.object(linear_service, "_sleep_before_retry") as mock_sleep,
        ):
            result = linear_service._graphql(
                "mutation { issueCreate }", retryable=False
            )

        assert result is None
        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()

    def test_no_retry_on_request_exception_when_retryable_is_false(
        self, linear_service
    ):
        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service,
                "_make_graphql_request",
                side_effect=requests.ConnectionError("timeout"),
            ) as mock_request,
            patch.object(linear_service, "_sleep_before_retry") as mock_sleep,
        ):
            result = linear_service._graphql(
                "mutation { issueCreate }", retryable=False
            )

        assert result is None
        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()

    def test_respects_configured_max_retries(self):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {
                "CLIENT_ID": "id",
                "CLIENT_SECRET": "secret",
                "MAX_RETRIES": 5,
            }
            svc = LinearService()

        assert svc.max_retries == 5

        transient_response = MagicMock()
        transient_response.status_code = 502
        transient_response.ok = False
        transient_response.text = "Bad Gateway"

        with (
            patch.object(svc, "_get_access_token", return_value="valid-token"),
            patch.object(
                svc,
                "_make_graphql_request",
                return_value=transient_response,
            ) as mock_request,
            patch.object(svc, "_sleep_before_retry") as mock_sleep,
        ):
            result = svc._graphql("query { viewer { id } }")

        assert result is None
        assert mock_request.call_count == 5
        assert mock_sleep.call_count == 4

    def test_respects_configured_retry_backoff_seconds(self):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {
                "CLIENT_ID": "id",
                "CLIENT_SECRET": "secret",
                "RETRY_BACKOFF_SECONDS": 0.5,
            }
            svc = LinearService()

        assert svc.retry_backoff_seconds == 0.5

        with patch("firetower.integrations.services.linear.time.sleep") as mock_sleep:
            svc._sleep_before_retry(0)
            mock_sleep.assert_called_once_with(0.5)

            mock_sleep.reset_mock()
            svc._sleep_before_retry(2)
            mock_sleep.assert_called_once_with(2.0)

    def test_uses_defaults_when_config_not_provided(self):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {
                "CLIENT_ID": "id",
                "CLIENT_SECRET": "secret",
            }
            svc = LinearService()

        assert svc.max_retries == LINEAR_DEFAULT_MAX_RETRIES
        assert svc.retry_backoff_seconds == LINEAR_DEFAULT_RETRY_BACKOFF_SECONDS

    @pytest.mark.parametrize("configured_value", [0, -1, -10])
    def test_clamps_max_retries_to_minimum_of_one(self, configured_value):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {
                "CLIENT_ID": "id",
                "CLIENT_SECRET": "secret",
                "MAX_RETRIES": configured_value,
            }
            svc = LinearService()

        assert svc.max_retries == 1

    def test_uses_default_timeout(self, linear_service):
        assert linear_service.timeout == LINEAR_DEFAULT_TIMEOUT_SECONDS

    def test_raises_linear_error_when_no_access_token(self, linear_service):
        with patch.object(linear_service, "_get_access_token", return_value=None):
            with pytest.raises(LinearError):
                linear_service._graphql("query { viewer { id } }", raise_on_error=True)

    def test_raises_linear_error_on_non_ok_response(self, linear_service):
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.ok = False
        error_response.text = "Internal Server Error"

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service, "_make_graphql_request", return_value=error_response
            ),
        ):
            with pytest.raises(LinearError):
                linear_service._graphql("query { viewer { id } }", raise_on_error=True)

    def test_raises_linear_error_on_graphql_errors(self, linear_service):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "some error"}],
            "data": None,
        }

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service, "_make_graphql_request", return_value=mock_response
            ),
        ):
            with pytest.raises(LinearError):
                linear_service._graphql("query { viewer { id } }", raise_on_error=True)

    def test_raises_linear_error_on_non_json_response(self, linear_service):
        # A 2xx whose body is not valid JSON must surface as LinearError for
        # raise_on_error callers, not let the ValueError from .json() propagate
        # and crash the allocator (which only expects LinearError).
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Expecting value")

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service, "_make_graphql_request", return_value=mock_response
            ),
        ):
            with pytest.raises(LinearError):
                linear_service._graphql("query { viewer { id } }", raise_on_error=True)

    def test_returns_none_on_non_json_response_when_not_raising(self, linear_service):
        # Default callers still get None (unchanged behavior), and it is not
        # retried (a broken body is not a transient transport error).
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Expecting value")

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service, "_make_graphql_request", return_value=mock_response
            ) as mock_req,
            patch.object(linear_service, "_sleep_before_retry") as mock_sleep,
        ):
            result = linear_service._graphql("query { viewer { id } }")

        assert result is None
        assert mock_req.call_count == 1
        mock_sleep.assert_not_called()

    def test_raises_linear_error_on_request_exception(self, linear_service):
        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service,
                "_make_graphql_request",
                side_effect=requests.ConnectionError("connection reset"),
            ),
            patch.object(linear_service, "_sleep_before_retry"),
        ):
            with pytest.raises(LinearError):
                linear_service._graphql("query { viewer { id } }", raise_on_error=True)

    def test_raises_linear_error_on_401_with_api_key(self, linear_service):
        linear_service.api_key = "lin_api_test"
        unauthorized_response = MagicMock()
        unauthorized_response.status_code = 401
        unauthorized_response.ok = False

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="lin_api_test"
            ),
            patch.object(
                linear_service,
                "_make_graphql_request",
                return_value=unauthorized_response,
            ),
        ):
            with pytest.raises(LinearError):
                linear_service._graphql("query { viewer { id } }", raise_on_error=True)

    def test_returns_data_when_result_absent_with_raise_on_error(self, linear_service):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"issue": None}}

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service, "_make_graphql_request", return_value=mock_response
            ),
        ):
            result = linear_service._graphql(
                "query { issue { id } }", raise_on_error=True
            )

        assert result == {"issue": None}

    def test_raises_linear_error_when_top_level_data_null(self, linear_service):
        # 200 OK with a null top-level "data" and no "errors" is anomalous, not
        # a genuine empty result; raise_on_error callers must not mistake it
        # for "not found".
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": None}

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service, "_make_graphql_request", return_value=mock_response
            ),
        ):
            with pytest.raises(LinearError):
                linear_service._graphql("query { issue { id } }", raise_on_error=True)

    def test_returns_none_when_top_level_data_null_without_raise(self, linear_service):
        # Default behavior unchanged: null top-level data still returns None.
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": None}

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service, "_make_graphql_request", return_value=mock_response
            ),
        ):
            result = linear_service._graphql("query { issue { id } }")

        assert result is None

    def test_raises_linear_error_when_data_key_missing(self, linear_service):
        # Same anomaly when the "data" key is omitted entirely.
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service, "_make_graphql_request", return_value=mock_response
            ),
        ):
            with pytest.raises(LinearError):
                linear_service._graphql("query { issue { id } }", raise_on_error=True)


class TestLinearBudget:
    def test_for_allocation_uses_settings_budget(self):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {"CLIENT_ID": "id", "CLIENT_SECRET": "secret"}
            mock_settings.INCIDENT_ALLOC_LINEAR_TIMEOUT = 8
            mock_settings.INCIDENT_ALLOC_LINEAR_RETRIES = 1
            svc = LinearService.for_allocation()

        assert svc.timeout == 8
        assert svc.max_retries == 1

    def test_constructor_overrides_timeout_and_retries(self):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {
                "CLIENT_ID": "id",
                "CLIENT_SECRET": "secret",
                "MAX_RETRIES": 5,
            }
            svc = LinearService(timeout=8, max_retries=1)

        assert svc.timeout == 8
        assert svc.max_retries == 1

    def test_tight_timeout_is_plumbed_into_request(self):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {"CLIENT_ID": "id", "CLIENT_SECRET": "secret"}
            svc = LinearService(timeout=8, max_retries=1)

        with patch("firetower.integrations.services.linear.requests.post") as mock_post:
            svc._make_graphql_request("query { viewer { id } }", None, "tok")

        _, kwargs = mock_post.call_args
        assert kwargs["timeout"] == 8

    @patch("firetower.integrations.services.linear.LinearOAuthToken")
    def test_tight_timeout_is_plumbed_into_token_request(self, mock_token_model):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {"CLIENT_ID": "id", "CLIENT_SECRET": "secret"}
            svc = LinearService(timeout=8, max_retries=1)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600,
        }

        with patch("firetower.integrations.services.linear.requests.post") as mock_post:
            mock_post.return_value = mock_response
            svc._request_new_token()

        _, kwargs = mock_post.call_args
        assert kwargs["timeout"] == 8

    def test_tight_retries_limit_attempts(self):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {"CLIENT_ID": "id", "CLIENT_SECRET": "secret"}
            svc = LinearService(timeout=8, max_retries=1)

        transient_response = MagicMock()
        transient_response.status_code = 502
        transient_response.ok = False
        transient_response.text = "Bad Gateway"

        with (
            patch.object(svc, "_get_access_token", return_value="valid-token"),
            patch.object(
                svc, "_make_graphql_request", return_value=transient_response
            ) as mock_request,
            patch.object(svc, "_sleep_before_retry") as mock_sleep,
        ):
            result = svc._graphql("query { viewer { id } }")

        assert result is None
        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()


class TestParseProjectNumber:
    @pytest.mark.parametrize(
        "identifier,expected",
        [
            ("INC-2353", 2353),
            ("INC-1", 1),
            ("INC-0", 0),
        ],
    )
    def test_matches_project_key(self, identifier, expected):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.PROJECT_KEY = "INC"
            assert parse_project_number(identifier) == expected

    @pytest.mark.parametrize(
        "identifier",
        [
            "PRODENG-1404",
            "INC-abc",
            "INC-12a",
            "INC-",
            "INC",
            "",
            "inc-2353",
            " INC-1",
            "INC-1 ",
            "XINC-1",
        ],
    )
    def test_returns_none_for_non_matches(self, identifier):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.PROJECT_KEY = "INC"
            assert parse_project_number(identifier) is None


class TestParseIssue:
    def test_parses_full_issue(self, linear_service):
        issue = {
            "id": "issue-1",
            "identifier": "ENG-123",
            "title": "Fix bug",
            "url": "https://linear.app/team/issue/ENG-123",
            "priority": 2,
            "state": {"type": "started"},
            "assignee": {"id": "user-1", "email": "alice@sentry.io"},
        }

        result = linear_service._parse_issue(issue)

        assert result == {
            "id": "issue-1",
            "identifier": "ENG-123",
            "title": "Fix bug",
            "url": "https://linear.app/team/issue/ENG-123",
            "status": "In Progress",
            "priority": 2,
            "assignee_email": "alice@sentry.io",
            "assignee_linear_id": "user-1",
            "relation_type": "child",
        }

    def test_maps_all_state_types(self, linear_service):
        for state_type, expected_status in [
            ("triage", "Todo"),
            ("backlog", "Todo"),
            ("unstarted", "Todo"),
            ("started", "In Progress"),
            ("completed", "Done"),
            ("canceled", "Canceled"),
        ]:
            issue = {
                "id": "i1",
                "identifier": "E-1",
                "title": "t",
                "url": "u",
                "state": {"type": state_type},
                "assignee": None,
            }
            assert linear_service._parse_issue(issue)["status"] == expected_status


class TestGetChildIssues:
    def test_paginates_through_multiple_pages(self, linear_service):
        with patch.object(
            linear_service,
            "_graphql",
            side_effect=[
                {
                    "issue": {
                        "children": {
                            "nodes": [
                                {
                                    "id": "c1",
                                    "identifier": "E-1",
                                    "title": "t",
                                    "url": "u",
                                    "state": {"type": "triage"},
                                    "assignee": None,
                                }
                            ],
                            "pageInfo": {"hasNextPage": True, "endCursor": "cursor1"},
                        }
                    }
                },
                {
                    "issue": {
                        "children": {
                            "nodes": [
                                {
                                    "id": "c2",
                                    "identifier": "E-2",
                                    "title": "t2",
                                    "url": "u2",
                                    "state": {"type": "completed"},
                                    "assignee": None,
                                }
                            ],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                },
            ],
        ) as mock_gql:
            result = linear_service.get_child_issues("parent-id")

        assert len(result) == 2
        assert result[0]["identifier"] == "E-1"
        assert result[1]["identifier"] == "E-2"
        second_call_vars = mock_gql.call_args_list[1][0][1]
        assert second_call_vars["after"] == "cursor1"


class TestGetUserByEmail:
    def test_returns_user_when_found(self, linear_service):
        mock_response = {
            "users": {
                "nodes": [
                    {"id": "user-123", "email": "alice@example.com"},
                ]
            }
        }

        with patch.object(linear_service, "_graphql", return_value=mock_response):
            result = linear_service.get_user_by_email("alice@example.com")

        assert result == {"id": "user-123", "email": "alice@example.com"}

    def test_returns_none_when_no_user_found(self, linear_service):
        mock_response = {"users": {"nodes": []}}

        with patch.object(linear_service, "_graphql", return_value=mock_response):
            result = linear_service.get_user_by_email("nobody@example.com")

        assert result is None

    def test_returns_none_on_api_failure(self, linear_service):
        with patch.object(linear_service, "_graphql", return_value=None):
            result = linear_service.get_user_by_email("alice@example.com")

        assert result is None


class TestGetIssue:
    def test_returns_issue_with_state_type(self, linear_service):
        mock_response = {
            "issue": {
                "id": "issue-123",
                "identifier": "LIN-42",
                "title": "Fix the thing",
                "url": "https://linear.app/team/issue/LIN-42",
                "priority": 1,
                "state": {"type": "started"},
                "assignee": {"id": "user-1", "email": "alice@example.com"},
            }
        }

        with patch.object(linear_service, "_graphql", return_value=mock_response):
            result = linear_service.get_issue("issue-123")

        assert result == {
            "id": "issue-123",
            "identifier": "LIN-42",
            "title": "Fix the thing",
            "url": "https://linear.app/team/issue/LIN-42",
            "state_type": "started",
        }

    def test_returns_empty_state_type_when_state_is_null(self, linear_service):
        mock_response = {
            "issue": {
                "id": "issue-123",
                "identifier": "LIN-42",
                "title": "Fix the thing",
                "url": "https://linear.app/team/issue/LIN-42",
                "priority": 1,
                "state": None,
                "assignee": None,
            }
        }

        with patch.object(linear_service, "_graphql", return_value=mock_response):
            result = linear_service.get_issue("issue-123")

        assert result is not None
        assert result["state_type"] == ""

    def test_returns_none_on_api_failure(self, linear_service):
        with patch.object(linear_service, "_graphql", return_value=None):
            result = linear_service.get_issue("issue-123")

        assert result is None

    def test_returns_none_when_issue_not_found(self, linear_service):
        mock_response = {"issue": None}

        with patch.object(linear_service, "_graphql", return_value=mock_response):
            result = linear_service.get_issue("nonexistent")

        assert result is None

    def test_returns_none_when_issue_null_even_with_raise_on_error(
        self, linear_service
    ):
        mock_response = {"issue": None}

        with patch.object(
            linear_service, "_graphql", return_value=mock_response
        ) as mock_gql:
            result = linear_service.get_issue("nonexistent", raise_on_error=True)

        assert result is None
        assert mock_gql.call_args.kwargs["raise_on_error"] is True

    def test_raises_linear_error_on_call_failure_when_raise_on_error(
        self, linear_service
    ):
        with patch.object(linear_service, "_graphql", side_effect=LinearError("boom")):
            with pytest.raises(LinearError):
                linear_service.get_issue("issue-123", raise_on_error=True)

    def test_returns_none_on_call_failure_when_not_raising(self, linear_service):
        with patch.object(linear_service, "_graphql", return_value=None) as mock_gql:
            result = linear_service.get_issue("issue-123")

        assert result is None
        assert mock_gql.call_args.kwargs["raise_on_error"] is False

    def test_raises_linear_error_when_top_level_data_null_end_to_end(
        self, linear_service
    ):
        # Exercises the real _graphql: a 200 with {"data": null} and no "errors"
        # must raise for raise_on_error callers rather than return None (which
        # would be indistinguishable from "issue genuinely absent").
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": None}

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service, "_make_graphql_request", return_value=mock_response
            ),
        ):
            with pytest.raises(LinearError):
                linear_service.get_issue("issue-123", raise_on_error=True)

    def _not_found_response(self):
        # Mirrors the real Linear response for an issue(id:) lookup against an
        # identifier that does not exist: HTTP 200 with a GraphQL "entity not
        # found" error and no data. Verified live: looking up an absent
        # TESTINC-N returns "Could not find referenced Issue." (RELENG-911).
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [
                {
                    "message": "Entity not found: Issue - Could not find "
                    "referenced Issue.",
                }
            ]
        }
        return mock_response

    def test_absent_identifier_returns_none_not_raises_end_to_end(self, linear_service):
        # THE RELENG-911 create_adopt bug: an absent placeholder slot must read
        # as "not found" (None), not as an error. Before the fix this raised
        # LinearError -> LinearUnavailable -> degraded on every mint.
        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service,
                "_make_graphql_request",
                return_value=self._not_found_response(),
            ),
        ):
            result = linear_service.get_issue("TESTINC-2189", raise_on_error=True)

        assert result is None

    def test_real_graphql_error_still_raises_end_to_end(self, linear_service):
        # A non-not-found error (e.g. auth/validation) must still raise for
        # raise_on_error callers, so the allocator degrades rather than clobber.
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [
                {
                    "message": "Authentication required",
                    "extensions": {"type": "authentication error"},
                }
            ]
        }

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service, "_make_graphql_request", return_value=mock_response
            ),
        ):
            with pytest.raises(LinearError):
                linear_service.get_issue("TESTINC-2189", raise_on_error=True)

    def test_mixed_errors_with_one_real_error_still_raises(self, linear_service):
        # If any error in the payload is not a not-found error, the whole
        # response is treated as a failure (raises), never swallowed as empty.
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [
                {"message": "Entity not found: Issue"},
                {"message": "Rate limit exceeded"},
            ]
        }

        with (
            patch.object(
                linear_service, "_get_access_token", return_value="valid-token"
            ),
            patch.object(
                linear_service, "_make_graphql_request", return_value=mock_response
            ),
        ):
            with pytest.raises(LinearError):
                linear_service.get_issue("TESTINC-2189", raise_on_error=True)


class TestErrorsAreNotFound:
    def test_issue_not_found_message(self):
        assert _errors_are_not_found(
            [{"message": "Entity not found: Issue - Could not find referenced Issue."}]
        )

    def test_case_insensitive(self):
        assert _errors_are_not_found([{"message": "COULD NOT FIND REFERENCED ISSUE"}])

    def test_other_not_found_entities_do_not_match(self):
        # Only a missing *issue* counts; team/user/etc. not-found must still
        # surface as a failure so the allocator degrades instead of minting.
        assert not _errors_are_not_found([{"message": "Team not found"}])
        assert not _errors_are_not_found(
            [{"message": "Could not find referenced User."}]
        )

    def test_real_error_is_not_not_found(self):
        assert not _errors_are_not_found([{"message": "Authentication required"}])

    def test_all_must_be_not_found(self):
        assert not _errors_are_not_found(
            [
                {"message": "Could not find referenced Issue."},
                {"message": "boom"},
            ]
        )

    def test_empty_or_malformed_is_not_not_found(self):
        assert not _errors_are_not_found([])
        assert not _errors_are_not_found(None)
        assert not _errors_are_not_found(["not a dict"])


class TestSummarizeGraphqlErrors:
    def test_renders_message_content(self):
        summary = _summarize_graphql_errors(
            [{"message": "Access denied", "extensions": {"code": "FORBIDDEN"}}]
        )
        assert "Access denied" in summary
        assert "FORBIDDEN" in summary

    def test_non_serializable_falls_back_to_repr(self):
        summary = _summarize_graphql_errors(object())
        assert summary  # does not raise, returns something

    def test_truncates_huge_payload(self):
        summary = _summarize_graphql_errors([{"message": "x" * 5000}])
        assert len(summary) < 5000
        assert summary.endswith("…[truncated]")
