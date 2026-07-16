import logging
import re
import time
from datetime import timedelta
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone

from firetower.integrations.models import LinearOAuthToken

logger = logging.getLogger(__name__)

LINEAR_API_URL = "https://api.linear.app/graphql"
LINEAR_TOKEN_URL = "https://api.linear.app/oauth/token"

LINEAR_STATE_TYPE_MAP = {
    "triage": "Todo",
    "backlog": "Todo",
    "unstarted": "Todo",
    "started": "In Progress",
    "completed": "Done",
    "canceled": "Canceled",
}

TOKEN_LIFETIME = timedelta(days=30)
TOKEN_REFRESH_BUFFER = timedelta(days=1)

# Transient failures (timeouts, gateway errors) from Linear are retried with
# exponential backoff before giving up, so brief upstream blips don't surface
# as errors.
LINEAR_RETRYABLE_STATUS_CODES = frozenset({502, 503, 504})
LINEAR_DEFAULT_MAX_RETRIES = 3
LINEAR_DEFAULT_RETRY_BACKOFF_SECONDS = 1.0
LINEAR_DEFAULT_TIMEOUT_SECONDS = 30

ISSUE_FIELDS = """
    id
    identifier
    title
    url
    priority
    state {
        type
    }
    assignee {
        id
        email
    }
"""


class LinearError(Exception):
    """Raised when a Linear API call fails outright.

    A "failure" means the call could not be completed successfully: a transport
    error, a non-OK HTTP response, a GraphQL ``errors`` payload, or a missing /
    invalid access token. It is distinct from a call that *succeeds* but returns
    an empty or absent result (e.g. an issue that genuinely does not exist),
    which callers observe as ``None``.
    """


# Exact message Linear returns when an ``issue(id:)`` lookup references an
# issue that does not exist. Matched case-insensitively. Deliberately specific
# to a missing *issue* (not a generic "not found") so unrelated errors
# (team/user/project not found, auth, etc.) still surface as failures rather
# than being mistaken for an empty issue lookup.
_ISSUE_NOT_FOUND_MESSAGE = "could not find referenced issue"


def _errors_are_not_found(errors: Any) -> bool:
    """True iff every GraphQL error in ``errors`` is an issue-not-found error.

    Linear responds to an ``issue(id:)`` lookup for a nonexistent identifier
    with a "Could not find referenced Issue." GraphQL error rather than a null
    result. We only treat the response as an empty (not-found) result when
    *all* returned errors are that specific issue-not-found error, so a
    response mixing a real failure with a not-found error still raises.
    """
    if not isinstance(errors, list) or not errors:
        return False
    for err in errors:
        if not isinstance(err, dict):
            return False
        if _ISSUE_NOT_FOUND_MESSAGE not in str(err.get("message", "")).lower():
            return False
    return True


def parse_project_number(identifier: str) -> int | None:
    """Return the integer N when ``identifier`` is exactly
    ``f"{settings.PROJECT_KEY}-<digits>"`` (e.g. ``"INC-2353"`` -> ``2353``),
    otherwise ``None`` (e.g. ``"PRODENG-1404"`` or ``"INC-abc"``).
    """
    match = re.fullmatch(rf"{re.escape(settings.PROJECT_KEY)}-(\d+)", identifier)
    if match is None:
        return None
    return int(match.group(1))


class LinearService:
    def __init__(
        self, *, timeout: int | None = None, max_retries: int | None = None
    ) -> None:
        assert settings.LINEAR is not None
        self.client_id = settings.LINEAR.get("CLIENT_ID")
        self.client_secret = settings.LINEAR.get("CLIENT_SECRET")
        self.api_key = settings.LINEAR.get("API_KEY")
        configured_max_retries = (
            max_retries
            if max_retries is not None
            else settings.LINEAR.get("MAX_RETRIES", LINEAR_DEFAULT_MAX_RETRIES)
        )
        self.max_retries: int = max(1, configured_max_retries)
        self.retry_backoff_seconds: float = settings.LINEAR.get(
            "RETRY_BACKOFF_SECONDS", LINEAR_DEFAULT_RETRY_BACKOFF_SECONDS
        )
        self.timeout: int = (
            timeout if timeout is not None else LINEAR_DEFAULT_TIMEOUT_SECONDS
        )
        self._workflow_states_cache: dict[str, str] | None = None

    @classmethod
    def for_allocation(cls) -> "LinearService":
        """Construct a service with the tight timeout/retry budget used by the
        incident allocation path.

        The allocator calls Linear while holding a DB lock, so it uses a bounded
        timeout and fewer retries than the default budget to ensure a hung or
        slow Linear can't hold the lock for the full default duration.
        """
        return cls(
            timeout=settings.INCIDENT_ALLOC_LINEAR_TIMEOUT,
            max_retries=settings.INCIDENT_ALLOC_LINEAR_RETRIES,
        )

    def _request_new_token(self) -> str | None:
        try:
            response = requests.post(
                LINEAR_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "read,write",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            access_token = data["access_token"]

            expires_in = data.get("expires_in")
            if expires_in is not None:
                expires_at = timezone.now() + timedelta(seconds=expires_in)
            else:
                expires_at = timezone.now() + TOKEN_LIFETIME

            LinearOAuthToken.objects.all().delete()
            LinearOAuthToken.objects.create(
                access_token=access_token,
                expires_at=expires_at,
            )

            logger.info("Obtained new Linear OAuth token")
            return access_token
        except requests.RequestException:
            logger.exception("Failed to obtain Linear OAuth token")
            return None
        except (KeyError, ValueError):
            logger.exception("Unexpected response from Linear token endpoint")
            return None

    def _get_access_token(self) -> str | None:
        if self.api_key:
            return self.api_key

        if not self.client_id or not self.client_secret:
            return None

        token = LinearOAuthToken.get_singleton()
        if token and token.expires_at > timezone.now() + TOKEN_REFRESH_BUFFER:
            return token.access_token

        return self._request_new_token()

    def _make_graphql_request(
        self, query: str, variables: dict | None, access_token: str
    ) -> requests.Response:
        auth_value = access_token if self.api_key else f"Bearer {access_token}"
        return requests.post(
            LINEAR_API_URL,
            json={"query": query, "variables": variables or {}},
            headers={
                "Authorization": auth_value,
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )

    def _raise_if_requested(self, message: str, *, raise_on_error: bool) -> None:
        """Raise ``LinearError`` when the caller opted in, otherwise do nothing.

        Lets a failed Linear call fall back to the historical ``None`` return
        while allowing opt-in callers to distinguish a failure from a genuine
        empty result.
        """
        if raise_on_error:
            raise LinearError(message)

    def _graphql(
        self,
        query: str,
        variables: dict | None = None,
        retryable: bool = True,
        *,
        raise_on_error: bool = False,
        not_found_is_empty: bool = False,
    ) -> dict | None:
        access_token = self._get_access_token()
        if not access_token:
            logger.warning(
                "Cannot make Linear API call - no valid access token available"
            )
            self._raise_if_requested(
                "No valid Linear access token available",
                raise_on_error=raise_on_error,
            )
            return None

        max_attempts = self.max_retries if retryable else 1
        for attempt in range(max_attempts):
            is_last_attempt = attempt == max_attempts - 1
            try:
                assert access_token is not None
                response = self._make_graphql_request(query, variables, access_token)

                if response.status_code == 401:
                    if self.api_key:
                        logger.error(
                            "Linear API returned 401 with api_key — key is invalid or expired"
                        )
                        self._raise_if_requested(
                            "Linear API returned 401 — api_key is invalid or expired",
                            raise_on_error=raise_on_error,
                        )
                        return None

                    logger.info("Linear token expired, requesting new token")
                    access_token = self._request_new_token()
                    if not access_token:
                        self._raise_if_requested(
                            "Linear token refresh failed after 401",
                            raise_on_error=raise_on_error,
                        )
                        return None

                    response = self._make_graphql_request(
                        query, variables, access_token
                    )

                if (
                    response.status_code in LINEAR_RETRYABLE_STATUS_CODES
                    and not is_last_attempt
                ):
                    self._sleep_before_retry(attempt)
                    continue

                if not response.ok:
                    logger.error(
                        "Linear API returned %d: %s",
                        response.status_code,
                        response.text,
                    )
                    self._raise_if_requested(
                        f"Linear API returned HTTP {response.status_code}",
                        raise_on_error=raise_on_error,
                    )
                    return None

                try:
                    data = response.json()
                except ValueError:
                    # A 2xx response whose body is not valid JSON is a broken
                    # response, not a transient transport error, so don't retry.
                    # Surface it as a failure (LinearError for raise_on_error
                    # callers) rather than letting the ValueError propagate and
                    # crash callers like the allocator, which only expect
                    # LinearError for Linear failures.
                    logger.exception("Linear API returned non-JSON response")
                    self._raise_if_requested(
                        "Linear API returned a non-JSON response",
                        raise_on_error=raise_on_error,
                    )
                    return None

                if "errors" in data:
                    # Looking up an issue by an identifier that does not exist
                    # (e.g. the placeholder slot the allocator wants to mint)
                    # comes back as a GraphQL "entity not found" error rather
                    # than a null result. When the caller asked for it, treat
                    # that specific case as a genuine empty result (None) so a
                    # missing issue is not mistaken for "Linear unreachable".
                    if not_found_is_empty and _errors_are_not_found(data["errors"]):
                        return None
                    logger.error(
                        "Linear GraphQL errors",
                        extra={"errors": data["errors"]},
                    )
                    self._raise_if_requested(
                        "Linear GraphQL response contained errors",
                        raise_on_error=raise_on_error,
                    )
                    return None

                result = data.get("data")
                if result is None:
                    # A 200 OK carrying a null/absent top-level "data" with no
                    # "errors" key is an anomalous/failed response, not a genuine
                    # empty result. Treat it as a failure so raise_on_error
                    # callers don't mistake it for "not found". Default callers
                    # still get None (unchanged behavior).
                    logger.error("Linear API returned no top-level data")
                    self._raise_if_requested(
                        "Linear API returned no data",
                        raise_on_error=raise_on_error,
                    )
                    return None
                return result
            except requests.RequestException:
                if not is_last_attempt:
                    self._sleep_before_retry(attempt)
                    continue
                logger.exception("Linear API request failed")
                self._raise_if_requested(
                    "Linear API request failed", raise_on_error=raise_on_error
                )
                return None

        self._raise_if_requested(
            "Linear API call failed", raise_on_error=raise_on_error
        )
        return None

    def _sleep_before_retry(self, attempt: int) -> None:
        time.sleep(self.retry_backoff_seconds * (2**attempt))

    def _parse_issue(
        self, issue: dict[str, Any], relation_type: str = "child"
    ) -> dict[str, Any]:
        state_type = (issue.get("state") or {}).get("type", "")
        status = LINEAR_STATE_TYPE_MAP.get(state_type, "Todo")
        assignee = issue.get("assignee") or {}
        return {
            "id": issue["id"],
            "identifier": issue["identifier"],
            "title": issue["title"],
            "url": issue["url"],
            "status": status,
            "priority": issue.get("priority", 0),
            "assignee_email": assignee.get("email"),
            "assignee_linear_id": assignee.get("id"),
            "relation_type": relation_type,
        }

    def get_issue(
        self, issue_id: str, *, raise_on_error: bool = False
    ) -> dict[str, Any] | None:
        """Fetch a Linear issue by id.

        By default (``raise_on_error=False``) any failure -- including the call
        failing outright -- is reported as ``None``, matching historical
        behavior. When ``raise_on_error=True``, ``None`` is returned *only* when
        the call succeeded and the issue is genuinely absent; a failed call
        raises :class:`LinearError` so callers can distinguish "not found" from
        "could not tell".
        """
        query = f"""
        query($id: String!) {{
            issue(id: $id) {{
                {ISSUE_FIELDS}
            }}
        }}
        """
        data = self._graphql(
            query,
            {"id": issue_id},
            raise_on_error=raise_on_error,
            not_found_is_empty=True,
        )
        if not data or not data.get("issue"):
            return None
        issue = data["issue"]
        return {
            "id": issue["id"],
            "identifier": issue["identifier"],
            "title": issue["title"],
            "url": issue["url"],
            "state_type": (issue.get("state") or {}).get("type", ""),
        }

    def get_user_by_email(self, email: str) -> dict[str, str] | None:
        query = """
        query($email: String!) {
            users(filter: { email: { eq: $email } }) {
                nodes {
                    id
                    email
                }
            }
        }
        """
        data = self._graphql(query, {"email": email})
        if not data:
            return None
        nodes = data.get("users", {}).get("nodes", [])
        if not nodes:
            return None
        return {"id": nodes[0]["id"], "email": nodes[0]["email"]}

    def create_issue(
        self,
        title: str,
        description: str,
        team_id: str,
        project_id: str | None = None,
        state_id: str | None = None,
        assignee_id: str | None = None,
    ) -> dict[str, Any] | None:
        mutation = """
        mutation($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    identifier
                    url
                }
            }
        }
        """
        input_data: dict[str, Any] = {
            "title": title,
            "description": description,
            "teamId": team_id,
        }
        if project_id:
            input_data["projectId"] = project_id
        if state_id:
            input_data["stateId"] = state_id
        if assignee_id:
            input_data["assigneeId"] = assignee_id

        data = self._graphql(mutation, {"input": input_data}, retryable=False)
        if not data:
            return None

        result = data.get("issueCreate", {})
        if not result.get("success"):
            logger.error("Linear issueCreate failed", extra={"result": result})
            return None

        issue = result.get("issue")
        if not issue:
            logger.error("Linear issueCreate returned no issue")
            return None

        return {
            "id": issue["id"],
            "identifier": issue["identifier"],
            "url": issue["url"],
        }

    def create_attachment(self, issue_id: str, url: str, title: str) -> bool:
        mutation = """
        mutation($input: AttachmentCreateInput!) {
            attachmentCreate(input: $input) {
                success
            }
        }
        """
        data = self._graphql(
            mutation,
            {"input": {"issueId": issue_id, "url": url, "title": title}},
            retryable=False,
        )
        if not data:
            return False

        return data.get("attachmentCreate", {}).get("success", False)

    def create_comment(self, issue_id: str, body: str) -> bool:
        mutation = """
        mutation($input: CommentCreateInput!) {
            commentCreate(input: $input) {
                success
            }
        }
        """
        data = self._graphql(
            mutation,
            {"input": {"issueId": issue_id, "body": body}},
            retryable=False,
        )
        if not data:
            return False

        return data.get("commentCreate", {}).get("success", False)

    def update_issue(
        self,
        issue_id: str,
        title: str | None = None,
        description: str | None = None,
        state_id: str | None = None,
        assignee_id: str | None = None,
    ) -> bool:
        mutation = """
        mutation($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
            }
        }
        """
        input_data: dict[str, Any] = {}
        if title is not None:
            input_data["title"] = title
        if description is not None:
            input_data["description"] = description
        if state_id is not None:
            input_data["stateId"] = state_id
        if assignee_id is not None:
            input_data["assigneeId"] = assignee_id

        if not input_data:
            return True

        data = self._graphql(
            mutation, {"id": issue_id, "input": input_data}, retryable=False
        )
        if not data:
            return False

        return data.get("issueUpdate", {}).get("success", False)

    def get_workflow_states(self, team_id: str) -> dict[str, str] | None:
        if self._workflow_states_cache is not None:
            return self._workflow_states_cache

        query = """
        query($teamId: String!) {
            team(id: $teamId) {
                states {
                    nodes {
                        id
                        name
                        type
                    }
                }
            }
        }
        """
        data = self._graphql(query, {"teamId": team_id})
        if not data:
            return None

        team = data.get("team")
        if not team:
            return None

        states: dict[str, str] = {}
        for node in team.get("states", {}).get("nodes", []):
            state_type = node.get("type", "")
            if state_type not in states:
                states[state_type] = node["id"]

        self._workflow_states_cache = states
        return states

    def get_child_issues(self, issue_id: str) -> list[dict[str, Any]] | None:
        query = f"""
        query($issueId: String!, $after: String) {{
            issue(id: $issueId) {{
                children(first: 50, after: $after) {{
                    nodes {{
                        {ISSUE_FIELDS}
                    }}
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                }}
            }}
        }}
        """

        issues: list[dict[str, Any]] = []
        cursor: str | None = None
        max_pages = 25

        for _ in range(max_pages):
            variables: dict[str, Any] = {"issueId": issue_id}
            if cursor is not None:
                variables["after"] = cursor

            data = self._graphql(query, variables)
            if data is None:
                return None

            issue = data.get("issue")
            if not issue:
                return None

            children = issue.get("children", {})
            issues.extend(
                self._parse_issue(node, "child") for node in children.get("nodes", [])
            )

            page_info = children.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
            if cursor is None:
                break

        return issues
