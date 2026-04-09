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

TOKEN_LIFETIME = timedelta(days=30)
TOKEN_REFRESH_BUFFER = timedelta(days=1)


class LinearService:
    def __init__(self) -> None:
        linear_config = settings.LINEAR
        self.client_id = linear_config.get("CLIENT_ID")
        self.client_secret = linear_config.get("CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            logger.warning("Linear OAuth credentials not configured")

    def _request_new_token(self) -> str | None:
        try:
            response = requests.post(
                LINEAR_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "read",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            access_token = data["access_token"]

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

    def _graphql(self, query: str, variables: dict | None = None) -> dict | None:
        access_token = self._get_access_token()
        if not access_token:
            logger.warning(
                "Cannot make Linear API call - no valid access token available"
            )
            return None

        try:
            response = requests.post(
                LINEAR_API_URL,
                json={"query": query, "variables": variables or {}},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )

            if response.status_code == 401:
                logger.info("Linear token expired, requesting new token")
                access_token = self._request_new_token()
                if not access_token:
                    return None

                response = requests.post(
                    LINEAR_API_URL,
                    json={"query": query, "variables": variables or {}},
                    headers={
                        "Authorization": f"Bearer {access_token}",
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
            attachmentsForURL(
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

            attachments = data.get("attachmentsForURL", {})

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
