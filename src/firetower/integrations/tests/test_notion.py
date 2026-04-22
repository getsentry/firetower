from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from firetower.integrations.services.notion import (
    NotionService,
    _build_appendable_blocks,
    _message_to_bullet,
    _strip_block,
)


@pytest.fixture
def notion():
    svc = NotionService(
        integration_token="test-key",
        database_id="db-id",
        template_id="tmpl-id",
    )
    svc.client = MagicMock()
    return svc


class TestGetUsers:
    def test_returns_email_to_user_map(self, notion):
        notion.client.users.list.return_value = {
            "results": [
                {"person": {"email": "a@sentry.io"}, "name": "Alice", "id": "U1"},
                {"person": {"email": "b@sentry.io"}, "name": "Bob", "id": "U2"},
                {
                    "object": "bot",
                    "name": "Integrations",
                    "id": "B1",
                },  # no "person" key
            ],
            "next_cursor": None,
        }

        users = notion.get_users()

        assert users == {
            "a@sentry.io": {"name": "Alice", "id": "U1"},
            "b@sentry.io": {"name": "Bob", "id": "U2"},
        }

    def test_paginates_until_no_next_cursor(self, notion):
        notion.client.users.list.side_effect = [
            {
                "results": [
                    {"person": {"email": "a@sentry.io"}, "name": "Alice", "id": "U1"}
                ],
                "next_cursor": "cursor1",
            },
            {
                "results": [
                    {"person": {"email": "b@sentry.io"}, "name": "Bob", "id": "U2"}
                ],
                "next_cursor": None,
            },
        ]

        users = notion.get_users()

        assert len(users) == 2
        assert notion.client.users.list.call_count == 2
        notion.client.users.list.assert_any_call(page_size=100, start_cursor="cursor1")

    def test_caches_result_on_second_call(self, notion):
        notion.client.users.list.return_value = {
            "results": [],
            "next_cursor": None,
        }

        notion.get_users()
        notion.get_users()

        notion.client.users.list.assert_called_once()


class TestFetchAllChildren:
    def test_returns_all_results_across_pages(self, notion):
        notion.client.blocks.children.list.side_effect = [
            {"results": [{"id": "b1"}], "next_cursor": "c1"},
            {"results": [{"id": "b2"}], "next_cursor": None},
        ]

        results = notion._fetch_all_children("parent-id")

        assert [r["id"] for r in results] == ["b1", "b2"]
        assert notion.client.blocks.children.list.call_count == 2


class TestAppendChildren:
    def test_returns_result_on_success(self, notion):
        notion.client.blocks.children.append.return_value = {"results": [{"id": "b1"}]}

        result = notion._append_children("block-id", [{"type": "paragraph"}])

        assert result == {"results": [{"id": "b1"}]}

    def test_retries_on_failure_then_succeeds(self, notion):
        notion.client.blocks.children.append.side_effect = [
            Exception("rate limited"),
            {"results": []},
        ]

        with patch("firetower.integrations.services.notion.time.sleep"):
            result = notion._append_children(
                "block-id", [{"type": "paragraph"}], max_retries=2
            )

        assert result == {"results": []}
        assert notion.client.blocks.children.append.call_count == 2

    def test_returns_none_after_max_retries(self, notion):
        notion.client.blocks.children.append.side_effect = Exception("always fails")

        with patch("firetower.integrations.services.notion.time.sleep"):
            result = notion._append_children(
                "block-id", [{"type": "paragraph"}], max_retries=2
            )

        assert result is None
        assert notion.client.blocks.children.append.call_count == 2


class TestMessageToBullet:
    def test_formats_message_correctly(self):
        msg = {
            "author": "alice@sentry.io",
            "date_time": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
            "text": "Hello world",
        }

        block = _message_to_bullet(msg)

        assert block["type"] == "bulleted_list_item"
        content = block["bulleted_list_item"]["rich_text"][0]["text"]["content"]
        assert content == "[2024-01-15 10:30 UTC] alice@sentry.io: Hello world"

    def test_truncates_long_messages(self):
        msg = {
            "author": "a@sentry.io",
            "date_time": datetime(2024, 1, 1, tzinfo=UTC),
            "text": "x" * 2100,
        }

        block = _message_to_bullet(msg)
        content = block["bulleted_list_item"]["rich_text"][0]["text"]["content"]
        assert len(content) <= 2000


class TestBuildAppendableBlocks:
    def test_strips_metadata_from_blocks(self):
        blocks = [
            {
                "id": "b1",
                "type": "paragraph",
                "created_time": "2024-01-01",
                "paragraph": {"rich_text": [{"text": {"content": "hello"}}]},
                "has_children": False,
            }
        ]

        result = _build_appendable_blocks(blocks, {})

        assert result == [
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": "hello"}}]},
            }
        ]

    def test_inlines_children_for_blocks_with_children(self):
        blocks = [
            {
                "id": "b1",
                "type": "toggle",
                "toggle": {"rich_text": []},
                "has_children": True,
            }
        ]
        children = {
            "b1": [
                {
                    "id": "c1",
                    "type": "paragraph",
                    "paragraph": {"rich_text": []},
                    "has_children": False,
                }
            ]
        }

        result = _build_appendable_blocks(blocks, children)

        assert result[0]["toggle"]["children"] == [
            {"type": "paragraph", "paragraph": {"rich_text": []}}
        ]

    def test_replaces_table_blocks_with_standard_schema(self):
        blocks = [
            {
                "id": "t1",
                "type": "table",
                "table": {"table_width": 3},
                "has_children": True,
            }
        ]

        result = _build_appendable_blocks(blocks, {})

        assert result[0]["type"] == "table"
        assert result[0]["table"]["table_width"] == 5
        assert result[0]["table"]["has_column_header"] is True


class TestStripBlock:
    def test_removes_metadata_keys(self):
        block = {
            "id": "abc",
            "type": "heading_1",
            "created_time": "2024-01-01",
            "heading_1": {"rich_text": [{"text": {"content": "Title"}}]},
        }

        result = _strip_block(block)

        assert result == {
            "type": "heading_1",
            "heading_1": {"rich_text": [{"text": {"content": "Title"}}]},
        }
