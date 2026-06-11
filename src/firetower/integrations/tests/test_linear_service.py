from datetime import timedelta
from unittest.mock import MagicMock, call, patch

import pytest
import requests
from django.utils import timezone

from firetower.integrations.services.linear import (
    LINEAR_DEFAULT_MAX_RETRIES,
    LINEAR_DEFAULT_RETRY_BACKOFF_SECONDS,
    LINEAR_TOKEN_URL,
    LinearService,
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


class TestGetRelatedIssues:
    def test_combines_forward_and_inverse_relations(self, linear_service):
        forward_response = {
            "issue": {
                "relations": {
                    "nodes": [
                        {
                            "type": "related",
                            "relatedIssue": {
                                "id": "r1",
                                "identifier": "E-1",
                                "title": "Related",
                                "url": "u1",
                                "state": {"type": "started"},
                                "assignee": None,
                            },
                        }
                    ],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }
        inverse_response = {
            "issue": {
                "inverseRelations": {
                    "nodes": [
                        {
                            "type": "blocks",
                            "issue": {
                                "id": "r2",
                                "identifier": "E-2",
                                "title": "Blocker",
                                "url": "u2",
                                "state": {"type": "unstarted"},
                                "assignee": None,
                            },
                        }
                    ],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }

        with patch.object(
            linear_service,
            "_graphql",
            side_effect=[forward_response, inverse_response],
        ):
            result = linear_service.get_related_issues("issue-1")

        assert len(result) == 2
        assert result[0]["identifier"] == "E-1"
        assert result[0]["relation_type"] == "related"
        assert result[1]["identifier"] == "E-2"
        assert result[1]["relation_type"] == "blocks"

    def test_deduplicates_across_forward_and_inverse(self, linear_service):
        shared_issue = {
            "id": "same-id",
            "identifier": "E-1",
            "title": "Same",
            "url": "u",
            "state": {"type": "started"},
            "assignee": None,
        }
        forward_response = {
            "issue": {
                "relations": {
                    "nodes": [{"type": "related", "relatedIssue": shared_issue}],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }
        inverse_response = {
            "issue": {
                "inverseRelations": {
                    "nodes": [{"type": "related", "issue": shared_issue}],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }

        with patch.object(
            linear_service,
            "_graphql",
            side_effect=[forward_response, inverse_response],
        ):
            result = linear_service.get_related_issues("issue-1")

        assert len(result) == 1


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
