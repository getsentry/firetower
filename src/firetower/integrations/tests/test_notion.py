from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from firetower.integrations.services.notion import (
    NotionService,
    _message_to_bullet,
    _users_cache,
)


@pytest.fixture
def notion():
    svc = NotionService(
        integration_token="test-key",
        database_id="db-id",
        template_markdown="# Template\n\nSome content.",
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
                {"object": "bot", "name": "Integrations", "id": "B1"},
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
        notion.client.users.list.return_value = {"results": [], "next_cursor": None}

        notion.get_users()
        notion.get_users()

        notion.client.users.list.assert_called_once()

    def test_module_cache_shared_across_instances(self, notion):
        notion.client.users.list.return_value = {
            "results": [
                {"person": {"email": "a@sentry.io"}, "name": "Alice", "id": "U1"}
            ],
            "next_cursor": None,
        }

        notion.get_users()

        second = NotionService(integration_token="test-key", database_id="db-id")
        second.client = MagicMock()
        second.get_users()

        second.client.users.list.assert_not_called()

    def test_retries_transient_errors_mid_pagination(self, notion):
        notion.client.users.list.side_effect = [
            {
                "results": [
                    {"person": {"email": "a@sentry.io"}, "name": "Alice", "id": "U1"}
                ],
                "next_cursor": "cursor1",
            },
            Exception("502 Bad Gateway"),
            {
                "results": [
                    {"person": {"email": "b@sentry.io"}, "name": "Bob", "id": "U2"}
                ],
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

    def test_tolerates_user_with_missing_name(self, notion):
        notion.client.users.list.return_value = {
            "results": [
                {"person": {"email": "a@sentry.io"}, "id": "U1"},  # no "name" key
            ],
            "next_cursor": None,
        }

        users = notion.get_users()

        assert users == {"a@sentry.io": {"name": "", "id": "U1"}}


class TestSendMarkdown:
    def test_sends_insert_content_patch(self, notion):
        with patch("firetower.integrations.services.notion.requests.patch") as mock_patch:
            mock_patch.return_value = MagicMock(status_code=200)
            mock_patch.return_value.raise_for_status = MagicMock()

            result = notion._send_markdown("page-id", "# Hello")

        assert result is True
        mock_patch.assert_called_once()
        call_kwargs = mock_patch.call_args
        assert "pages/page-id/markdown" in call_kwargs.args[0]
        assert call_kwargs.kwargs["json"] == {
            "type": "insert_content",
            "insert_content": {"content": "# Hello"},
        }

    def test_retries_on_failure_then_succeeds(self, notion):
        mock_response = MagicMock(status_code=200)
        mock_response.raise_for_status = MagicMock()

        with patch("firetower.integrations.services.notion.requests.patch") as mock_patch:
            mock_patch.side_effect = [Exception("rate limited"), mock_response]

            with patch("firetower.integrations.services.notion.time.sleep"):
                result = notion._send_markdown("page-id", "content", max_retries=2)

        assert result is True
        assert mock_patch.call_count == 2

    def test_returns_false_after_max_retries(self, notion):
        with patch("firetower.integrations.services.notion.requests.patch") as mock_patch:
            mock_patch.side_effect = Exception("always fails")

            with patch("firetower.integrations.services.notion.time.sleep"):
                result = notion._send_markdown("page-id", "content", max_retries=2)

        assert result is False
        assert mock_patch.call_count == 2


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
    def test_uses_date_mention_for_timestamp(self):
        dt = datetime(2024, 1, 15, 10, 30, tzinfo=UTC)
        msg = {"author": "alice@sentry.io", "date_time": dt, "text": "Hello world"}

        block = _message_to_bullet(msg)

        rich_text = block["bulleted_list_item"]["rich_text"]
        assert rich_text[0]["type"] == "mention"
        assert rich_text[0]["mention"]["type"] == "date"
        assert rich_text[0]["mention"]["date"]["start"] == dt.isoformat()

    def test_appends_author_and_text_after_mention(self):
        dt = datetime(2024, 1, 15, 10, 30, tzinfo=UTC)
        msg = {"author": "alice@sentry.io", "date_time": dt, "text": "Hello world"}

        block = _message_to_bullet(msg)

        suffix = block["bulleted_list_item"]["rich_text"][1]["text"]["content"]
        assert suffix == " alice@sentry.io: Hello world"

    def test_truncates_long_suffix(self):
        dt = datetime(2024, 1, 1, tzinfo=UTC)
        msg = {"author": "a@sentry.io", "date_time": dt, "text": "x" * 2100}

        block = _message_to_bullet(msg)

        suffix = block["bulleted_list_item"]["rich_text"][1]["text"]["content"]
        assert len(suffix) <= 2000


class TestUploadFileToNotion:
    def test_returns_upload_id_on_success(self, notion):
        create_response = MagicMock()
        create_response.json.return_value = {"id": "upload-123"}
        create_response.raise_for_status = MagicMock()
        send_response = MagicMock()
        send_response.raise_for_status = MagicMock()

        with patch("firetower.integrations.services.notion.requests.post") as mock_post:
            mock_post.side_effect = [create_response, send_response]
            result = notion._upload_file_to_notion(b"IMG", "image.png", "image/png")

        assert result == "upload-123"
        assert mock_post.call_count == 2
        create_call, send_call = mock_post.call_args_list
        assert "file_uploads" in create_call.args[0]
        assert "file_uploads/upload-123/send" in send_call.args[0]

    def test_returns_none_when_create_fails(self, notion):
        with patch(
            "firetower.integrations.services.notion.requests.post",
            side_effect=Exception("500"),
        ):
            result = notion._upload_file_to_notion(b"IMG", "image.png", "image/png")

        assert result is None

    def test_returns_none_when_send_fails(self, notion):
        create_response = MagicMock()
        create_response.json.return_value = {"id": "upload-123"}
        create_response.raise_for_status = MagicMock()

        with patch("firetower.integrations.services.notion.requests.post") as mock_post:
            mock_post.side_effect = [create_response, Exception("413 too large")]
            result = notion._upload_file_to_notion(b"IMG", "image.png", "image/png")

        assert result is None


class TestCreateImageBlock:
    def test_returns_image_block_on_success(self, notion):
        with patch.object(notion, "_upload_file_to_notion", return_value="upload-abc"):
            block = notion._create_image_block(
                {"data": b"PNG", "content_type": "image/png"}
            )

        assert block == {
            "type": "image",
            "image": {"type": "file_upload", "file_upload": {"id": "upload-abc"}},
        }

    def test_returns_none_when_upload_fails(self, notion):
        with patch.object(notion, "_upload_file_to_notion", return_value=None):
            block = notion._create_image_block(
                {"data": b"PNG", "content_type": "image/png"}
            )

        assert block is None

    def test_returns_none_when_data_missing(self, notion):
        block = notion._create_image_block({"content_type": "image/png"})
        assert block is None

    def test_adds_clickable_caption_when_source_url_present(self, notion):
        with patch.object(notion, "_upload_file_to_notion", return_value="upload-abc"):
            block = notion._create_image_block(
                {
                    "data": b"PNG",
                    "content_type": "image/png",
                    "source_url": "https://app.datadoghq.com/dashboard/abc",
                }
            )

        caption = block["image"]["caption"]
        assert len(caption) == 1
        assert (
            caption[0]["text"]["content"] == "https://app.datadoghq.com/dashboard/abc"
        )
        assert (
            caption[0]["text"]["link"]["url"]
            == "https://app.datadoghq.com/dashboard/abc"
        )

    def test_omits_caption_when_source_url_empty(self, notion):
        with patch.object(notion, "_upload_file_to_notion", return_value="upload-abc"):
            block = notion._create_image_block(
                {"data": b"PNG", "content_type": "image/png", "source_url": ""}
            )

        assert "caption" not in block["image"]


class TestApplyTemplate:
    def _make_append_response(self, block_id: str) -> dict:
        return {"results": [{"id": block_id}]}

    def test_new_page_sends_markdown_then_slack_blocks(self, notion):
        notion.client.blocks.children.append.return_value = self._make_append_response(
            "toggle-id"
        )

        with patch.object(notion, "_send_markdown", return_value=True) as mock_md:
            notion.apply_template("page-id", messages=[], update_slack=False)

        mock_md.assert_called_once_with("page-id", "# Template\n\nSome content.")
        notion.client.blocks.children.append.assert_called_once()
        toggle_block = notion.client.blocks.children.append.call_args.kwargs[
            "children"
        ][0]
        assert toggle_block["type"] == "toggle"

    def test_raises_when_send_markdown_fails(self, notion):
        notion.client.blocks.children.append.return_value = self._make_append_response(
            "toggle-id"
        )

        with (
            patch.object(notion, "_send_markdown", return_value=False),
            pytest.raises(RuntimeError, match="template"),
        ):
            notion.apply_template("page-id", messages=[], update_slack=False)

    def test_raises_when_toggle_creation_fails(self, notion):
        with (
            patch.object(notion, "_send_markdown", return_value=True),
            patch.object(notion, "_append_children", return_value=None),
            pytest.raises(RuntimeError, match="toggle"),
        ):
            notion.apply_template("page-id", messages=[], update_slack=False)

    def test_update_slack_skips_markdown_template(self, notion):
        notion.client.blocks.children.append.return_value = self._make_append_response(
            "toggle-id"
        )

        with patch.object(notion, "_send_markdown", return_value=True) as mock_md:
            notion.apply_template("page-id", messages=[], update_slack=True)

        mock_md.assert_not_called()

    def test_appends_replies_as_children_of_parent_bullet(self, notion):
        notion.client.blocks.children.append.side_effect = [
            {"results": [{"id": "toggle-id"}]},
            {"results": [{"id": "bullet-id"}]},
            {"results": [{"id": "reply-id"}]},
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

        with patch.object(notion, "_send_markdown", return_value=True):
            notion.apply_template("page-id", messages=messages, update_slack=True)

        reply_call = notion.client.blocks.children.append.call_args_list[2]
        assert reply_call.kwargs["block_id"] == "bullet-id"

    def test_appends_images_before_replies_as_children_of_bullet(self, notion):
        notion.client.blocks.children.append.side_effect = [
            {"results": [{"id": "toggle-id"}]},
            {"results": [{"id": "bullet-id"}]},
            {"results": [{"id": "children-id"}]},
        ]
        image_block = {
            "type": "image",
            "image": {"type": "file_upload", "file_upload": {"id": "upload-1"}},
        }
        messages = [
            {
                "author": "a@sentry.io",
                "date_time": datetime(2024, 1, 1, tzinfo=UTC),
                "text": "check this graph",
                "images": [{"data": b"PNG", "content_type": "image/png"}],
                "replies": [
                    {
                        "author": "b@sentry.io",
                        "date_time": datetime(2024, 1, 1, 0, 1, tzinfo=UTC),
                        "text": "reply",
                    }
                ],
            }
        ]

        with (
            patch.object(notion, "_send_markdown", return_value=True),
            patch.object(notion, "_create_image_block", return_value=image_block),
        ):
            notion.apply_template("page-id", messages=messages, update_slack=True)

        children_call = notion.client.blocks.children.append.call_args_list[2]
        assert children_call.kwargs["block_id"] == "bullet-id"
        appended = children_call.kwargs["children"]
        assert appended[0]["type"] == "image"
        assert appended[1]["type"] == "bulleted_list_item"

    def test_skips_failed_image_uploads(self, notion):
        notion.client.blocks.children.append.side_effect = [
            {"results": [{"id": "toggle-id"}]},
            {"results": [{"id": "bullet-id"}]},
        ]
        messages = [
            {
                "author": "a@sentry.io",
                "date_time": datetime(2024, 1, 1, tzinfo=UTC),
                "text": "check this graph",
                "images": [{"data": b"PNG", "content_type": "image/png"}],
                "replies": [],
            }
        ]

        with (
            patch.object(notion, "_send_markdown", return_value=True),
            patch.object(notion, "_create_image_block", return_value=None),
        ):
            notion.apply_template("page-id", messages=messages, update_slack=True)

        # Only 2 appends: toggle creation + bullet batch. No children call since image failed.
        assert notion.client.blocks.children.append.call_count == 2

    def test_batches_children_at_block_limit(self, notion):
        notion.client.blocks.children.append.side_effect = [
            {"results": [{"id": "toggle-id"}]},
            {"results": [{"id": "bullet-id"}]},
            {"results": []},
            {"results": []},
        ]
        reply_bullet = {
            "author": "b@sentry.io",
            "date_time": datetime(2024, 1, 1, 0, 1, tzinfo=UTC),
            "text": "reply",
        }
        messages = [
            {
                "author": "a@sentry.io",
                "date_time": datetime(2024, 1, 1, tzinfo=UTC),
                "text": "main",
                "images": [],
                "replies": [reply_bullet] * 90,
            }
        ]

        with patch.object(notion, "_send_markdown", return_value=True):
            notion.apply_template("page-id", messages=messages, update_slack=True)

        # 4 total: toggle, bullet batch, first 85 replies, last 5 replies
        assert notion.client.blocks.children.append.call_count == 4
        assert (
            len(
                notion.client.blocks.children.append.call_args_list[2].kwargs[
                    "children"
                ]
            )
            == 85
        )
        assert (
            len(
                notion.client.blocks.children.append.call_args_list[3].kwargs[
                    "children"
                ]
            )
            == 5
        )

    def test_logs_warning_when_notion_returns_fewer_ids_than_batch(self, notion):
        # Notion returns 1 block ID for a batch of 2 bullets.
        notion.client.blocks.children.append.side_effect = [
            {"results": [{"id": "toggle-id"}]},
            {"results": [{"id": "bullet-1"}]},  # only 1 result for 2 bullets
            {"results": []},  # reply append for bullet-1
        ]
        messages = [
            {
                "author": "a@sentry.io",
                "date_time": datetime(2024, 1, 1, tzinfo=UTC),
                "text": "msg1",
                "images": [],
                "replies": [
                    {
                        "author": "b@sentry.io",
                        "date_time": datetime(2024, 1, 1, 0, 1, tzinfo=UTC),
                        "text": "reply",
                    },
                ],
            },
            {
                "author": "a@sentry.io",
                "date_time": datetime(2024, 1, 1, 1, tzinfo=UTC),
                "text": "msg2",
                "images": [],
                "replies": [
                    {
                        "author": "b@sentry.io",
                        "date_time": datetime(2024, 1, 1, 1, 1, tzinfo=UTC),
                        "text": "reply2",
                    },
                ],
            },
        ]

        with (
            patch.object(notion, "_send_markdown", return_value=True),
            patch("firetower.integrations.services.notion.logger") as mock_logger,
        ):
            notion.apply_template("page-id", messages=messages, update_slack=True)

        # Confirm the mismatch warning was emitted.
        warning_args = [call[0][0] for call in mock_logger.warning.call_args_list]
        assert any("block IDs" in msg for msg in warning_args)
        # Only bullet-1's reply is appended; msg2's reply is skipped (no block ID).
        assert notion.client.blocks.children.append.call_count == 3

    def test_aborts_and_logs_error_when_create_slack_content_makes_no_progress(
        self, notion
    ):
        notion.client.blocks.children.append.return_value = {
            "results": [{"id": "toggle-id"}]
        }
        messages = [
            {
                "author": "a@sentry.io",
                "date_time": datetime(2024, 1, 1, tzinfo=UTC),
                "text": "msg",
                "images": [],
                "replies": [],
            }
        ]
        with (
            patch.object(notion, "_send_markdown", return_value=True),
            patch(
                "firetower.integrations.services.notion._create_slack_content",
                return_value=(0, []),  # stopping_index == index == 0: no progress
            ),
            patch("firetower.integrations.services.notion.logger") as mock_logger,
        ):
            notion.apply_template("page-id", messages=messages, update_slack=True)

        error_args = [call[0][0] for call in mock_logger.error.call_args_list]
        assert any("no progress" in msg for msg in error_args)
        # append called once for the toggle; never called again for bullets
        assert notion.client.blocks.children.append.call_count == 1

    def test_logs_warning_when_batch_append_returns_none(self, notion):
        # Toggle append succeeds; bullet batch append exhausts retries → None
        notion.client.blocks.children.append.side_effect = [
            {"results": [{"id": "toggle-id"}]},
            None,
        ]
        messages = [
            {
                "author": "a@sentry.io",
                "date_time": datetime(2024, 1, 1, tzinfo=UTC),
                "text": "msg",
                "images": [],
                "replies": [],
            }
        ]

        with (
            patch.object(notion, "_send_markdown", return_value=True),
            patch("firetower.integrations.services.notion.logger") as mock_logger,
        ):
            notion.apply_template("page-id", messages=messages, update_slack=True)

        warning_args = [call[0][0] for call in mock_logger.warning.call_args_list]
        assert any("absent from the Notion dump" in msg for msg in warning_args)
