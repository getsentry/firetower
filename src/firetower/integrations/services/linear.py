import logging
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

LINEAR_RELATION_TYPE_MAP = {
    "related": "related",
    "blocks": "blocks",
    "blocked": "blocked_by",
    "duplicate": "duplicate",
}

TOKEN_LIFETIME = timedelta(days=30)
TOKEN_REFRESH_BUFFER = timedelta(days=1)

# Transient failures (timeouts, gateway errors) from Linear are retried with
# exponential backoff before giving up, so brief upstream blips don't surface
# as errors.
LINEAR_RETRYABLE_STATUS_CODES = frozenset({502, 503, 504})
LINEAR_MAX_RETRIES = 3
LINEAR_RETRY_BACKOFF_SECONDS = 1.0

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


class LinearService:
    def __init__(self) -> None:
        assert settings.LINEAR is not None
        self.client_id = settings.LINEAR.get("CLIENT_ID")
        self.client_secret = settings.LINEAR.get("CLIENT_SECRET")
        self.api_key = settings.LINEAR.get("API_KEY")
        self._workflow_states_cache: dict[str, str] | None = None

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
                timeout=30,
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
            timeout=30,
        )

    def _graphql(
        self,
        query: str,
        variables: dict | None = None,
        retryable: bool = True,
    ) -> dict | None:
        access_token = self._get_access_token()
        if not access_token:
            logger.warning(
                "Cannot make Linear API call - no valid access token available"
            )
            return None

        max_attempts = LINEAR_MAX_RETRIES if retryable else 1
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
                        return None

                    logger.info("Linear token expired, requesting new token")
                    access_token = self._request_new_token()
                    if not access_token:
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
                    return None

                data = response.json()

                if "errors" in data:
                    logger.error(
                        "Linear GraphQL errors",
                        extra={"errors": data["errors"]},
                    )
                    return None

                return data.get("data")
            except requests.RequestException:
                if not is_last_attempt:
                    self._sleep_before_retry(attempt)
                    continue
                logger.exception("Linear API request failed")
                return None

        return None

    @staticmethod
    def _sleep_before_retry(attempt: int) -> None:
        time.sleep(LINEAR_RETRY_BACKOFF_SECONDS * (2**attempt))

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

    def get_issue(self, issue_id: str) -> dict[str, Any] | None:
        query = f"""
        query($id: String!) {{
            issue(id: $id) {{
                {ISSUE_FIELDS}
            }}
        }}
        """
        data = self._graphql(query, {"id": issue_id})
        if not data or not data.get("issue"):
            return None
        issue = data["issue"]
        return {
            "id": issue["id"],
            "identifier": issue["identifier"],
            "title": issue["title"],
            "url": issue["url"],
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

    def _fetch_relations(
        self,
        issue_id: str,
        field: str,
        issue_key: str,
        seen_ids: set[str],
    ) -> list[dict[str, Any]] | None:
        query = f"""
        query($issueId: String!, $after: String) {{
            issue(id: $issueId) {{
                {field}(first: 50, after: $after) {{
                    nodes {{
                        type
                        {issue_key} {{
                            {ISSUE_FIELDS}
                        }}
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

            relations = issue.get(field, {})
            for node in relations.get("nodes", []):
                related_issue = node.get(issue_key)
                if not related_issue or "id" not in related_issue:
                    continue
                if related_issue["id"] in seen_ids:
                    continue
                seen_ids.add(related_issue["id"])

                linear_type = node.get("type", "").lower()
                relation_type = LINEAR_RELATION_TYPE_MAP.get(linear_type, "related")
                issues.append(self._parse_issue(related_issue, relation_type))

            page_info = relations.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
            if cursor is None:
                break

        return issues

    def get_related_issues(self, issue_id: str) -> list[dict[str, Any]] | None:
        seen_ids: set[str] = set()

        forward = self._fetch_relations(issue_id, "relations", "relatedIssue", seen_ids)
        if forward is None:
            return None

        inverse = self._fetch_relations(issue_id, "inverseRelations", "issue", seen_ids)
        if inverse is None:
            return None

        return forward + inverse
