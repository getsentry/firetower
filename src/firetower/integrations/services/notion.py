import logging
import time
from datetime import UTC, datetime
from typing import Any, cast

import requests
import sentry_sdk
from notion_client import Client

from firetower.integrations.services.slack import is_slack_url

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
    @classmethod
    def is_configured(cls) -> bool:
        from django.conf import settings  # noqa: PLC0415

        config = settings.NOTION
        return bool(
            config and config.get("INTEGRATION_TOKEN") and config.get("DATABASE_ID")
        )

    @classmethod
    def from_settings(cls) -> "NotionService | None":
        from django.conf import settings  # noqa: PLC0415

        config = settings.NOTION
        if (
            not config
            or not config.get("INTEGRATION_TOKEN")
            or not config.get("DATABASE_ID")
        ):
            return None
        return cls(
            integration_token=config["INTEGRATION_TOKEN"],
            database_id=config["DATABASE_ID"],
            template_markdown=config.get("TEMPLATE_MARKDOWN", ""),
        )

    def __init__(
        self, integration_token: str, database_id: str, template_markdown: str = ""
    ) -> None:
        self.client: Client = Client(
            auth=integration_token, notion_version=_MARKDOWN_NOTION_VERSION
        )
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
                        users[email] = {"name": user.get("name", ""), "id": user["id"]}
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
            if not self._send_markdown(page_id, self.template_markdown):
                raise RuntimeError(
                    f"Failed to apply markdown template to Notion page {page_id}"
                )

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
        if response is None or not response.get("results"):
            raise RuntimeError(
                f"Failed to append slack toggle to Notion page {page_id}"
            )
        toggle_id = response["results"][0]["id"]

        index = 0
        while index < len(messages):
            stopping_index, batch = _create_slack_content(messages, index)
            if stopping_index <= index:
                logger.error(
                    "_create_slack_content made no progress at index %d for page %s, aborting",
                    index,
                    page_id,
                )
                break
            response = self._append_children(toggle_id, batch)
            if response is None:
                logger.warning(
                    "Appending bullet batch (messages %d-%d) to page %s failed after retries; "
                    "those messages will be absent from the Notion dump.",
                    index,
                    stopping_index - 1,
                    page_id,
                )
            else:
                batch_size = stopping_index - index
                returned = len(response["results"])
                if returned < batch_size:
                    logger.warning(
                        "Notion returned %d block IDs for %d appended bullets "
                        "on page %s; images and replies for %d message(s) will be skipped.",
                        returned,
                        batch_size,
                        page_id,
                        batch_size - returned,
                    )
                slack_index = index
                notion_index = 0
                while slack_index < stopping_index and notion_index < returned:
                    slack_msg = messages[slack_index]
                    children: list[dict[str, Any]] = []
                    for img in slack_msg.get("images", []):
                        block = self._create_image_block(img)
                        if block is not None:
                            children.append(block)
                    children.extend(
                        _message_to_bullet(r) for r in slack_msg.get("replies", [])
                    )
                    bullet_id = response["results"][notion_index]["id"]
                    for i in range(0, len(children), _BLOCK_CHILD_LIMIT):
                        self._append_children(
                            bullet_id, children[i : i + _BLOCK_CHILD_LIMIT]
                        )
                    slack_index += 1
                    notion_index += 1
            index = stopping_index

    def _send_markdown(self, page_id: str, content: str, max_retries: int = 3) -> bool:
        # notion-client v3 does not wrap the Markdown API endpoint, so we call it directly.
        for attempt in range(max_retries):
            try:
                response = requests.patch(
                    f"{_NOTION_API_BASE}/pages/{page_id}/markdown",
                    headers={
                        "Authorization": f"Bearer {self._integration_token}",
                        "Notion-Version": _MARKDOWN_NOTION_VERSION,
                    },
                    json={
                        "type": "insert_content",
                        "insert_content": {"content": content},
                    },
                    timeout=60.0,
                )
                response.raise_for_status()
                return True
            except Exception as exc:
                if attempt == max_retries - 1:
                    logger.error(
                        "Max retries reached sending markdown to Notion page %s",
                        page_id,
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

    def _upload_file_to_notion(
        self, data: bytes, filename: str, content_type: str
    ) -> str | None:
        auth_headers = {
            "Authorization": f"Bearer {self._integration_token}",
            "Notion-Version": _MARKDOWN_NOTION_VERSION,
        }
        try:
            create_resp = requests.post(
                f"{_NOTION_API_BASE}/file_uploads",
                headers={**auth_headers, "Content-Type": "application/json"},
                json={"filename": filename},
                timeout=30.0,
            )
            create_resp.raise_for_status()
            upload_id = create_resp.json()["id"]
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.warning("Failed to create Notion file upload: %s", exc)
            return None
        try:
            send_resp = requests.post(
                f"{_NOTION_API_BASE}/file_uploads/{upload_id}/send",
                headers=auth_headers,
                files={"file": (filename, data, content_type)},
                timeout=60.0,
            )
            send_resp.raise_for_status()
            return upload_id
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.warning(
                "Failed to send file to Notion upload %s: %s", upload_id, exc
            )
            return None

    def _create_image_block(self, image: dict[str, Any]) -> dict[str, Any] | None:
        data = image.get("data")
        content_type = image.get("content_type", "image/png")
        image_url = image.get("image_url", "")
        source_url = image.get("source_url", "")
        if not data:
            return None
        ext = content_type.split("/")[-1] if "/" in content_type else "png"
        upload_id = self._upload_file_to_notion(data, f"image.{ext}", content_type)
        if upload_id:
            image_content: dict[str, Any] = {
                "type": "file_upload",
                "file_upload": {"id": upload_id},
            }
        elif image_url and not is_slack_url(image_url):
            image_content = {"type": "external", "external": {"url": image_url}}
        else:
            return None
        if source_url:
            image_content["caption"] = [
                {
                    "type": "text",
                    "text": {"content": source_url, "link": {"url": source_url}},
                }
            ]
        return {"type": "image", "image": image_content}

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
                if attempt == max_retries - 1:
                    break
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
