import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

LINEAR_API_URL = "https://api.linear.app/graphql"

LINEAR_STATE_TYPE_MAP = {
    "triage": "Todo",
    "backlog": "Todo",
    "unstarted": "Todo",
    "started": "In Progress",
    "completed": "Done",
    "cancelled": "Cancelled",
}


class LinearService:
    def __init__(self) -> None:
        linear_config = settings.LINEAR
        self.api_key = linear_config.get("API_KEY")

        if not self.api_key:
            logger.warning("Linear API key not configured")

    def _graphql(self, query: str, variables: dict | None = None) -> dict | None:
        if not self.api_key:
            logger.warning("Cannot make Linear API call - API key not configured")
            return None

        try:
            response = requests.post(
                LINEAR_API_URL,
                json={"query": query, "variables": variables or {}},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
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

    def get_issues_by_attachment_url(
        self, url_contains: str
    ) -> list[dict[str, Any]] | None:
        query = """
        query($url_contains: String!, $after: String) {
            attachments(
                first: 50,
                after: $after,
                filter: { url: { contains: $url_contains } }
            ) {
                nodes {
                    issue {
                        id
                        identifier
                        title
                        url
                        state {
                            type
                        }
                        assignee {
                            email
                        }
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
        """

        issues: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        cursor: str | None = None
        max_pages = 25
        page = 0

        while page < max_pages:
            page += 1
            variables: dict[str, Any] = {"url_contains": url_contains}
            if cursor is not None:
                variables["after"] = cursor

            data = self._graphql(query, variables)
            if data is None:
                return None

            attachments = data.get("attachments", {})

            for node in attachments.get("nodes", []):
                issue = node.get("issue")
                if not issue or issue["id"] in seen_ids:
                    continue
                seen_ids.add(issue["id"])

                state_type = issue.get("state", {}).get("type", "")
                status = LINEAR_STATE_TYPE_MAP.get(state_type, "Todo")

                assignee_email = None
                if issue.get("assignee"):
                    assignee_email = issue["assignee"].get("email")

                issues.append(
                    {
                        "id": issue["id"],
                        "identifier": issue["identifier"],
                        "title": issue["title"],
                        "url": issue["url"],
                        "status": status,
                        "assignee_email": assignee_email,
                    }
                )

            page_info = attachments.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
            if cursor is None:
                break

        logger.info(
            f"Found {len(issues)} Linear issues for URL containing '{url_contains}'"
        )
        return issues
