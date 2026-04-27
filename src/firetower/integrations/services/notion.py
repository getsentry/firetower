import logging
import time
from datetime import UTC, datetime
from typing import Any, cast

import httpx
from notion_client import Client

logger = logging.getLogger(__name__)

_NOTION_API_BASE = "https://api.notion.com/v1"
# Markdown API requires a newer version than the library default.
_MARKDOWN_NOTION_VERSION = "2026-03-11"

_BLOCK_CHILD_LIMIT = 85  # Notion enforces a hard limit of 100; stay below for safety
_NOTION_RICH_TEXT_LIMIT = 2000

# Module-level cache so the full user-list pagination (7+ pages for large workspaces)
# only runs once per process rather than once per command invocation.
_users_cache: dict[str, dict[str, dict[str, str]]] = {}


class NotionService:
    def __init__(
        self, integration_token: str, database_id: str, template_markdown: str = ""
    ) -> None:
        self.client: Client = Client(auth=integration_token)
        self._integration_token = integration_token
        self.database_id = database_id
        self.template_markdown = template_markdown
        self._users: dict[str, dict[str, str]] | None = None

    def get_users(self) -> dict[str, dict[str, str]]:
        """Return email -> {name, id} for all Notion workspace users."""
        if self._users is not None:
            return self._users

        cached = _users_cache.get(self._integration_token)
        if cached is not None:
            self._users = cached
            return cached

        users: dict[str, dict[str, str]] = {}
        start_cursor: str | None = None

        while True:
            kwargs: dict[str, Any] = {"page_size": 100}
            if start_cursor:
                kwargs["start_cursor"] = start_cursor

            for attempt in range(3):
                try:
                    response = cast(dict[str, Any], self.client.users.list(**kwargs))
                    break
                except Exception as exc:
                    if attempt == 2:
                        raise
                    wait = 2**attempt
                    logger.warning(
                        "Notion users.list failed (attempt %d/3): %s. Retrying in %ds.",
                        attempt + 1,
                        exc,
                        wait,
                    )
                    time.sleep(wait)

            for user in response.get("results", []):
                if "person" in user:
                    email = user["person"].get("email", "")
                    if email:
                        users[email] = {"name": user["name"], "id": user["id"]}
            start_cursor = response.get("next_cursor")
            if not start_cursor:
                break

        _users_cache[self._integration_token] = users
        self._users = users
        return users

    def create_postmortem_page(
        self,
        incident_number: str,
        incident_title: str,
        incident_url: str,
        incident_date: datetime,
        severity: str | None = None,
        captain_email: str | None = None,
    ) -> dict[str, Any]:
        properties: dict[str, Any] = {
            "Name": {
                "title": [
                    {
                        "type": "text",
                        "text": {"content": f"[{incident_number}] {incident_title}"},
                    }
                ]
            },
            "Incident": {"url": incident_url},
            "Inc Date": {"date": {"start": incident_date.date().isoformat()}},
        }

        if severity:
            properties["Severity"] = {"select": {"name": severity}}

        if captain_email:
            notion_user = self.get_users().get(captain_email)
            if notion_user:
                properties["Incident Captain"] = {
                    "people": [{"object": "user", "id": notion_user["id"]}]
                }

        logger.debug("Creating Notion page with database_id=%r", self.database_id)
        return cast(
            dict[str, Any],
            self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties,
            ),
        )

    def apply_template(
        self,
        page_id: str,
        messages: list[dict[str, Any]],
        update_slack: bool = False,
    ) -> None:
        if not update_slack and self.template_markdown:
            self._send_markdown(page_id, self.template_markdown)

        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        toggle: dict[str, Any] = {
            "type": "toggle",
            "toggle": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": (
                                f"Slack channel discussions as of {timestamp}. "
                                "This should not be used in place of the Timeline."
                            )
                        },
                    }
                ],
                "color": "default",
                "children": [],
            },
        }
        response = self._append_children(page_id, [toggle])
        if response is None:
            logger.error(
                "Failed to append slack toggle to page %s, aborting slack dump", page_id
            )
            return
        toggle_id = response["results"][0]["id"]

        index = 0
        while index < len(messages):
            stopping_index, batch = _create_slack_content(messages, index)
            response = self._append_children(toggle_id, batch)
            if response is not None:
                slack_index = index
                notion_index = 0
                while (
                    slack_index < len(messages)
                    and notion_index < len(response["results"])
                ):
                    slack_msg = messages[slack_index]
                    if slack_msg.get("replies"):
                        reply_blocks = [_message_to_bullet(r) for r in slack_msg["replies"]]
                        self._append_children(
                            response["results"][notion_index]["id"], reply_blocks
                        )
                    slack_index += 1
                    notion_index += 1
            index = stopping_index

    def _send_markdown(self, page_id: str, content: str, max_retries: int = 3) -> bool:
        # notion-client v3 does not wrap the Markdown API endpoint, so we call it directly.
        for attempt in range(max_retries):
            try:
                response = httpx.patch(
                    f"{_NOTION_API_BASE}/pages/{page_id}/markdown",
                    headers={
                        "Authorization": f"Bearer {self._integration_token}",
                        "Notion-Version": _MARKDOWN_NOTION_VERSION,
                    },
                    json={"type": "insert_content", "insert_content": {"content": content}},
                    timeout=60.0,
                )
                response.raise_for_status()
                return True
            except Exception as exc:
                if attempt == max_retries - 1:
                    logger.error(
                        "Max retries reached sending markdown to Notion page %s", page_id
                    )
                    return False
                wait = 2**attempt
                logger.warning(
                    "Notion markdown send failed (attempt %d/%d): %s. Retrying in %ds.",
                    attempt + 1,
                    max_retries,
                    exc,
                    wait,
                )
                time.sleep(wait)
        return False

    def _append_children(
        self,
        block_id: str,
        children: list[dict[str, Any]],
        max_retries: int = 3,
    ) -> dict[str, Any] | None:
        for attempt in range(max_retries):
            try:
                return cast(
                    dict[str, Any],
                    self.client.blocks.children.append(
                        block_id=block_id, children=children
                    ),
                )
            except Exception as exc:
                wait = 2**attempt
                logger.warning(
                    "Notion append failed (attempt %d/%d): %s. Retrying in %ds.",
                    attempt + 1,
                    max_retries,
                    exc,
                    wait,
                )
                time.sleep(wait)
        logger.error(
            "Max retries reached appending children to Notion block %s", block_id
        )
        return None


def _create_slack_content(
    messages: list[dict[str, Any]], starting_index: int
) -> tuple[int, list[dict[str, Any]]]:
    bullets: list[dict[str, Any]] = []
    index = starting_index
    while index < len(messages) and len(bullets) < _BLOCK_CHILD_LIMIT:
        bullets.append(_message_to_bullet(messages[index]))
        index += 1
    return index, bullets


def _message_to_bullet(msg: dict[str, Any]) -> dict[str, Any]:
    dt: datetime = msg["date_time"]
    author = msg.get("author") or "unknown"
    text = msg.get("text") or ""
    suffix = f" {author}: {text}"[:_NOTION_RICH_TEXT_LIMIT]
    return {
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [
                {
                    "type": "mention",
                    "mention": {
                        "type": "date",
                        "date": {"start": dt.isoformat()},
                    },
                },
                {
                    "type": "text",
                    "text": {"content": suffix},
                },
            ]
        },
    }
