from datetime import UTC, datetime
from unittest.mock import MagicMock, call, patch

import pytest

from firetower.integrations.services.notion import (
    NotionService,
    _clean_block,
    _message_to_bullet,
    _users_cache,
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
    @pytest.fixture(autouse=True)
    def clear_users_cache(self):
        _users_cache.pop("test-key", None)
        yield
        _users_cache.pop("test-key", None)

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

    def test_module_cache_shared_across_instances(self, notion):
        notion.client.users.list.return_value = {
            "results": [{"person": {"email": "a@sentry.io"}, "name": "Alice", "id": "U1"}],
            "next_cursor": None,
        }

        notion.get_users()

        second = NotionService(
            integration_token="test-key", database_id="db-id"
        )
        second.client = MagicMock()
        second.get_users()

        second.client.users.list.assert_not_called()

    def test_retries_transient_errors_mid_pagination(self, notion):
        notion.client.users.list.side_effect = [
            {
                "results": [{"person": {"email": "a@sentry.io"}, "name": "Alice", "id": "U1"}],
                "next_cursor": "cursor1",
            },
            Exception("502 Bad Gateway"),
            {
                "results": [{"person": {"email": "b@sentry.io"}, "name": "Bob", "id": "U2"}],
                "next_cursor": None,
            },
        ]

        with patch("firetower.integrations.services.notion.time.sleep"):
            users = notion.get_users()

        assert len(users) == 2
        assert notion.client.users.list.call_count == 3

    def test_raises_after_max_retries(self, notion):
        notion.client.users.list.side_effect = [
            {"results": [], "next_cursor": "cursor1"},
            Exception("502"),
            Exception("502"),
            Exception("502"),
        ]

        with patch("firetower.integrations.services.notion.time.sleep"):
            with pytest.raises(Exception, match="502"):
                notion.get_users()


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

    def test_retries_on_404(self, notion):
        notion.client.blocks.children.append.side_effect = [
            Exception("object_not_found"),
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


class TestCleanBlock:
    def test_removes_archived_and_in_trash(self):
        block = {
            "id": "b1",
            "type": "paragraph",
            "archived": False,
            "in_trash": False,
            "paragraph": {"rich_text": []},
        }

        result = _clean_block(block)

        assert "archived" not in result
        assert "in_trash" not in result
        assert result["id"] == "b1"
        assert result["type"] == "paragraph"

    def test_preserves_all_other_keys(self):
        block = {
            "id": "b1",
            "type": "heading_1",
            "created_time": "2024-01-01",
            "heading_1": {"rich_text": [{"text": {"content": "Title"}}]},
        }

        result = _clean_block(block)

        assert result == block


class TestApplyTemplate:
    def _make_append_response(self, block_id: str, block_type: str = "paragraph") -> dict:
        return {"results": [{"id": block_id, "type": block_type}]}

    def test_skips_template_when_update_slack(self, notion):
        notion.client.blocks.children.append.return_value = self._make_append_response(
            "toggle-id", "toggle"
        )

        notion.apply_template(
            "page-id", template=[{"type": "paragraph", "id": "t1", "paragraph": {}}],
            template_children={}, messages=[], update_slack=True,
        )

        # Only the toggle append should happen, not the template block
        assert notion.client.blocks.children.append.call_count == 1
        args = notion.client.blocks.children.append.call_args
        assert args.kwargs["children"][0]["type"] == "toggle"

    def test_appends_template_blocks_one_at_a_time(self, notion):
        notion.client.blocks.children.append.return_value = self._make_append_response(
            "new-id", "paragraph"
        )

        template = [
            {"id": "t1", "type": "paragraph", "paragraph": {"rich_text": []}},
            {"id": "t2", "type": "heading_1", "heading_1": {"rich_text": []}},
        ]

        notion.apply_template(
            "page-id", template=template, template_children={}, messages=[], update_slack=False,
        )

        # 2 template blocks + 1 toggle = 3 calls
        assert notion.client.blocks.children.append.call_count == 3

    def test_appends_replies_as_children_of_parent_bullet(self, notion):
        notion.client.blocks.children.append.side_effect = [
            # toggle append
            {"results": [{"id": "toggle-id", "type": "toggle"}]},
            # batch of 1 message
            {"results": [{"id": "bullet-id", "type": "bulleted_list_item"}]},
            # replies append
            {"results": [{"id": "reply-id", "type": "bulleted_list_item"}]},
        ]

        messages = [
            {
                "author": "a@sentry.io",
                "date_time": datetime(2024, 1, 1, tzinfo=UTC),
                "text": "main",
                "replies": [
                    {
                        "author": "b@sentry.io",
                        "date_time": datetime(2024, 1, 1, 0, 1, tzinfo=UTC),
                        "text": "reply",
                    }
                ],
            }
        ]

        notion.apply_template(
            "page-id", template=[], template_children={}, messages=messages, update_slack=True,
        )

        # Third call should append the reply to the bullet block ID
        reply_call = notion.client.blocks.children.append.call_args_list[2]
        assert reply_call.kwargs["block_id"] == "bullet-id"
