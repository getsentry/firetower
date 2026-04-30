import logging
from datetime import timedelta
from typing import Any

import requests
from django.conf import settings
from django.db import transaction
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
    "cancelled": "Cancelled",
}

LINEAR_RELATION_TYPE_MAP = {
    "related": "related",
    "blocks": "blocks",
    "blocked": "blocked_by",
    "duplicate": "duplicate",
}

TOKEN_LIFETIME = timedelta(days=30)
TOKEN_REFRESH_BUFFER = timedelta(days=1)

ISSUE_FIELDS = """
    id
    identifier
    title
    url
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
        linear_config = settings.LINEAR
        self.client_id = linear_config.get("CLIENT_ID")
        self.client_secret = linear_config.get("CLIENT_SECRET")
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

            with transaction.atomic():
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
        if not self.client_id or not self.client_secret:
            return None

        token = LinearOAuthToken.get_singleton()
        if token and token.expires_at > timezone.now() + TOKEN_REFRESH_BUFFER:
            return token.access_token

        return self._request_new_token()

    def _make_graphql_request(
        self, query: str, variables: dict | None, access_token: str
    ) -> requests.Response:
        return requests.post(
            LINEAR_API_URL,
            json={"query": query, "variables": variables or {}},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )

    def _graphql(self, query: str, variables: dict | None = None) -> dict | None:
        access_token = self._get_access_token()
        if not access_token:
            logger.warning(
                "Cannot make Linear API call - no valid access token available"
            )
            return None

        try:
            response = self._make_graphql_request(query, variables, access_token)

            if response.status_code == 401:
                logger.info("Linear token expired, requesting new token")
                access_token = self._request_new_token()
                if not access_token:
                    return None

                response = self._make_graphql_request(query, variables, access_token)

            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                logger.error(
                    "Linear GraphQL errors",
                    extra={"errors": data["errors"]},
                )
                return None

            return data.get("data")
        except requests.RequestException as e:
            logger.error(f"Linear API request failed: {e}")
            return None

    def _parse_issue(
        self, issue: dict[str, Any], relation_type: str = "child"
    ) -> dict[str, Any]:
        state_type = issue.get("state", {}).get("type", "")
        status = LINEAR_STATE_TYPE_MAP.get(state_type, "Todo")
        assignee = issue.get("assignee") or {}
        return {
            "id": issue["id"],
            "identifier": issue["identifier"],
            "title": issue["title"],
            "url": issue["url"],
            "status": status,
            "assignee_email": assignee.get("email"),
            "assignee_linear_id": assignee.get("id"),
            "relation_type": relation_type,
        }

    def create_issue(
        self,
        title: str,
        description: str,
        team_id: str,
        project_id: str | None = None,
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

        data = self._graphql(mutation, {"input": input_data})
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
        )
        if not data:
            return False

        return data.get("attachmentCreate", {}).get("success", False)

    def update_issue(
        self,
        issue_id: str,
        title: str | None = None,
        state_id: str | None = None,
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
        if state_id is not None:
            input_data["stateId"] = state_id

        if not input_data:
            return True

        data = self._graphql(mutation, {"id": issue_id, "input": input_data})
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

    def get_related_issues(self, issue_id: str) -> list[dict[str, Any]] | None:
        query = f"""
        query($issueId: String!, $after: String) {{
            issue(id: $issueId) {{
                relations(first: 50, after: $after) {{
                    nodes {{
                        type
                        relatedIssue {{
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
        seen_ids: set[str] = set()
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

            relations = issue.get("relations", {})
            for node in relations.get("nodes", []):
                related_issue = node.get("relatedIssue")
                if not related_issue or related_issue["id"] in seen_ids:
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
