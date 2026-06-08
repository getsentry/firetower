from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from slack_sdk.errors import SlackApiError

from firetower.incidents.models import ExternalLinkType, Incident, IncidentSeverity
from firetower.integrations.services.slack import SlackService, is_slack_url
from firetower.slack_app.handlers.dumpslack import (
    _backfill_milestones,
    _download_image,
    _extract_image_urls,
    _extract_notion_page_id,
    _get_channel_messages,
    _resolve_user_emails,
    _trigger_slack_dump,
    handle_dumpslack_command,
)


class TestExtractNotionPageId:
    def test_extracts_id_without_hyphens(self):
        url = "https://www.notion.so/sentry/Title-abc123def456abc123def456abc123de"
        result = _extract_notion_page_id(url)
        assert result == "abc123de-f456-abc1-23de-f456abc123de"

    def test_extracts_uuid_with_hyphens(self):
        url = "https://www.notion.so/abc123de-f456-abc1-23de-f456abc123de"
        result = _extract_notion_page_id(url)
        assert result == "abc123de-f456-abc1-23de-f456abc123de"

    def test_returns_none_for_invalid_url(self):
        assert _extract_notion_page_id("https://notion.so/no-id-here") is None

    def test_handles_trailing_slash(self):
        url = "https://www.notion.so/sentry/Title-abc123def456abc123def456abc123de/"
        result = _extract_notion_page_id(url)
        assert result == "abc123de-f456-abc1-23de-f456abc123de"


class TestResolveUserEmails:
    def _mock_profile(self, external_id, email):
        p = MagicMock()
        p.external_id = external_id
        p.user.email = email
        return p

    def test_returns_emails_from_db(self):
        service = MagicMock(spec=SlackService)
        with patch("firetower.slack_app.handlers.dumpslack.ExternalProfile") as mock_ep:
            mock_ep.objects.filter.return_value.select_related.return_value = [
                self._mock_profile("U1", "u1@sentry.io")
            ]
            result = _resolve_user_emails(service, {"U1"})

        assert result == {"U1": "u1@sentry.io"}
        service.get_user_info.assert_not_called()

    def test_falls_back_to_users_info_for_unknown_ids(self):
        service = MagicMock(spec=SlackService)
        service.get_user_info.return_value = {"email": "fallback@sentry.io"}
        with patch("firetower.slack_app.handlers.dumpslack.ExternalProfile") as mock_ep:
            mock_ep.objects.filter.return_value.select_related.return_value = []
            result = _resolve_user_emails(service, {"U_UNKNOWN"})

        assert result == {"U_UNKNOWN": "fallback@sentry.io"}
        service.get_user_info.assert_called_once_with("U_UNKNOWN")

    def test_falls_back_to_slack_id_when_user_info_returns_none(self):
        service = MagicMock(spec=SlackService)
        service.get_user_info.return_value = None
        with patch("firetower.slack_app.handlers.dumpslack.ExternalProfile") as mock_ep:
            mock_ep.objects.filter.return_value.select_related.return_value = []
            result = _resolve_user_emails(service, {"U_MISSING"})

        assert result == {"U_MISSING": "U_MISSING"}

    def test_mixes_db_and_api_results(self):
        service = MagicMock(spec=SlackService)
        service.get_user_info.return_value = {"email": "unknown@sentry.io"}
        with patch("firetower.slack_app.handlers.dumpslack.ExternalProfile") as mock_ep:
            mock_ep.objects.filter.return_value.select_related.return_value = [
                self._mock_profile("U1", "known@sentry.io")
            ]
            result = _resolve_user_emails(service, {"U1", "U2"})

        assert result["U1"] == "known@sentry.io"
        assert result["U2"] == "unknown@sentry.io"


class TestGetChannelMessages:
    def _make_service(self, messages=None, replies=None):
        service = MagicMock(spec=SlackService)
        service.bot_token = ""
        service.get_channel_history.return_value = messages or []
        service.get_thread_replies.return_value = replies or []
        return service

    def test_filters_bots_and_system_messages(self):
        service = self._make_service(
            messages=[
                {
                    "type": "message",
                    "user": "U1",
                    "text": "real message",
                    "ts": "1000000000.000000",
                },
                {
                    "type": "message",
                    "user": "U2",
                    "text": "bot msg",
                    "ts": "1000000001.000000",
                    "bot_id": "B1",
                },
                {
                    "type": "message",
                    "user": "U3",
                    "text": "joined",
                    "ts": "1000000002.000000",
                    "subtype": "channel_join",
                },
                {"type": "message", "user": "U4", "ts": "1000000003.000000"},
            ]
        )

        with patch(
            "firetower.slack_app.handlers.dumpslack._resolve_user_emails",
            return_value={"U1": "user@sentry.io"},
        ):
            messages = _get_channel_messages(service, "C123")

        assert len(messages) == 1
        assert messages[0]["text"] == "real message"

    def test_returns_chronological_order(self):
        service = self._make_service(
            messages=[
                {
                    "type": "message",
                    "user": "U1",
                    "text": "second",
                    "ts": "1000000002.000000",
                },
                {
                    "type": "message",
                    "user": "U1",
                    "text": "first",
                    "ts": "1000000001.000000",
                },
            ]
        )

        with patch(
            "firetower.slack_app.handlers.dumpslack._resolve_user_emails",
            return_value={"U1": "user@sentry.io"},
        ):
            messages = _get_channel_messages(service, "C123")

        assert messages[0]["text"] == "first"
        assert messages[1]["text"] == "second"

    def test_returns_empty_when_no_messages(self):
        service = self._make_service(messages=[])
        messages = _get_channel_messages(service, "C123")
        assert messages == []

    def test_fetches_thread_replies(self):
        service = self._make_service(
            messages=[
                {
                    "type": "message",
                    "user": "U1",
                    "text": "parent",
                    "ts": "1000000001.000000",
                    "thread_ts": "1000000001.000000",
                    "reply_count": 1,
                },
            ],
            replies=[
                {
                    "type": "message",
                    "user": "U2",
                    "text": "reply",
                    "ts": "1000000002.000000",
                },
            ],
        )

        with patch(
            "firetower.slack_app.handlers.dumpslack._resolve_user_emails",
            return_value={"U1": "u1@sentry.io", "U2": "u2@sentry.io"},
        ):
            messages = _get_channel_messages(service, "C123")

        assert len(messages) == 1
        assert len(messages[0]["replies"]) == 1
        assert messages[0]["replies"][0]["text"] == "reply"
        service.get_thread_replies.assert_called_once_with("C123", "1000000001.000000")

    def test_includes_image_only_messages(self):
        service = self._make_service(
            messages=[
                {
                    "type": "message",
                    "user": "U1",
                    "text": "",
                    "ts": "1000000001.000000",
                    "attachments": [{"image_url": "https://p.datadoghq.com/graph.png"}],
                },
            ]
        )

        with (
            patch(
                "firetower.slack_app.handlers.dumpslack._download_image",
                return_value=None,
            ),
            patch(
                "firetower.slack_app.handlers.dumpslack._resolve_user_emails",
                return_value={"U1": "user@sentry.io"},
            ),
        ):
            messages = _get_channel_messages(service, "C123")

        assert len(messages) == 1


class TestExtractImageUrls:
    def test_extracts_attachment_image_url_with_source(self):
        msg = {
            "attachments": [
                {
                    "image_url": "https://p.datadoghq.com/img/graph.png",
                    "title_link": "https://app.datadoghq.com/dashboard/abc",
                }
            ]
        }
        assert _extract_image_urls(msg) == [
            {
                "image_url": "https://p.datadoghq.com/img/graph.png",
                "source_url": "https://app.datadoghq.com/dashboard/abc",
            }
        ]

    def test_falls_back_to_from_url_when_no_title_link(self):
        msg = {
            "attachments": [
                {
                    "image_url": "https://p.datadoghq.com/img/graph.png",
                    "from_url": "https://app.datadoghq.com/dashboard/xyz",
                }
            ]
        }
        result = _extract_image_urls(msg)
        assert result[0]["source_url"] == "https://app.datadoghq.com/dashboard/xyz"

    def test_source_url_empty_when_no_link_fields(self):
        msg = {"attachments": [{"image_url": "https://p.datadoghq.com/img/graph.png"}]}
        result = _extract_image_urls(msg)
        assert result == [
            {"image_url": "https://p.datadoghq.com/img/graph.png", "source_url": ""}
        ]

    def test_extracts_slack_file_url_with_empty_source(self):
        msg = {
            "files": [
                {
                    "mimetype": "image/png",
                    "url_private": "https://files.slack.com/files-pri/T1/screenshot.png",
                }
            ]
        }
        assert _extract_image_urls(msg) == [
            {
                "image_url": "https://files.slack.com/files-pri/T1/screenshot.png",
                "source_url": "",
            }
        ]

    def test_skips_non_image_files(self):
        msg = {
            "files": [
                {
                    "mimetype": "application/pdf",
                    "url_private": "https://files.slack.com/doc.pdf",
                }
            ]
        }
        assert _extract_image_urls(msg) == []

    def test_skips_attachments_without_image_url(self):
        msg = {"attachments": [{"text": "some text", "fallback": "fallback"}]}
        assert _extract_image_urls(msg) == []

    def test_returns_empty_for_message_with_no_attachments_or_files(self):
        msg = {"text": "hello", "user": "U1"}
        assert _extract_image_urls(msg) == []

    def test_extracts_top_level_image_block(self):
        msg = {
            "blocks": [
                {
                    "type": "image",
                    "image_url": "https://example.com/graph.png",
                    "alt_text": "graph",
                }
            ]
        }
        assert _extract_image_urls(msg) == [
            {"image_url": "https://example.com/graph.png", "source_url": ""}
        ]

    def test_extracts_image_accessory_from_section_block(self):
        msg = {
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "some text"},
                    "accessory": {
                        "type": "image",
                        "image_url": "https://example.com/thumb.png",
                        "alt_text": "thumbnail",
                    },
                }
            ]
        }
        assert _extract_image_urls(msg) == [
            {"image_url": "https://example.com/thumb.png", "source_url": ""}
        ]

    def test_extracts_image_element_from_context_block(self):
        msg = {
            "blocks": [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "image",
                            "image_url": "https://example.com/icon.png",
                            "alt_text": "icon",
                        },
                        {"type": "mrkdwn", "text": "some context"},
                    ],
                }
            ]
        }
        assert _extract_image_urls(msg) == [
            {"image_url": "https://example.com/icon.png", "source_url": ""}
        ]

    def test_skips_blocks_without_images(self):
        msg = {
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": "hello"}},
                {"type": "divider"},
            ]
        }
        assert _extract_image_urls(msg) == []


class TestIsSlackUrl:
    def test_matches_files_slack_com(self):
        assert is_slack_url("https://files.slack.com/files-pri/T1/img.jpg") is True

    def test_matches_slack_com_subdomain(self):
        assert is_slack_url("https://slack-edge.com/img.png") is False
        assert is_slack_url("https://something.slack.com/path") is True

    def test_rejects_slack_com_in_path(self):
        assert is_slack_url("https://evil.com/slack.com/img.png") is False

    def test_rejects_slack_com_as_subdomain_of_attacker(self):
        assert is_slack_url("https://slack.com.evil.com/img.png") is False

    def test_rejects_non_slack_url(self):
        assert is_slack_url("https://p.datadoghq.com/img/graph.png") is False


class TestDownloadImage:
    def _mock_session(self, response=None, side_effect=None):
        mock_session = MagicMock()
        if side_effect is not None:
            mock_session.get.side_effect = side_effect
        else:
            mock_session.get.return_value = response
        return mock_session

    def test_downloads_external_image_without_auth(self):
        mock_response = MagicMock()
        mock_response.content = b"PNG_DATA"
        mock_response.headers = {"content-type": "image/png"}
        mock_response.raise_for_status = MagicMock()
        mock_session = self._mock_session(response=mock_response)

        with patch(
            "firetower.slack_app.handlers.dumpslack.requests.Session",
            return_value=mock_session,
        ):
            result = _download_image(
                "https://p.datadoghq.com/img/graph.png", "xoxb-token"
            )

        assert result == (b"PNG_DATA", "image/png")
        call_headers = mock_session.get.call_args.kwargs["headers"]
        assert "Authorization" not in call_headers

    def test_adds_slack_bearer_token_for_slack_urls(self):
        mock_response = MagicMock()
        mock_response.content = b"IMG"
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.raise_for_status = MagicMock()
        mock_session = self._mock_session(response=mock_response)

        with patch(
            "firetower.slack_app.handlers.dumpslack.requests.Session",
            return_value=mock_session,
        ):
            _download_image(
                "https://files.slack.com/files-pri/T1/img.jpg", "xoxb-token"
            )

        call_headers = mock_session.get.call_args.kwargs["headers"]
        assert call_headers["Authorization"] == "Bearer xoxb-token"

    def test_returns_none_on_request_failure(self):
        mock_session = self._mock_session(side_effect=Exception("timeout"))

        with patch(
            "firetower.slack_app.handlers.dumpslack.requests.Session",
            return_value=mock_session,
        ):
            result = _download_image("https://example.com/img.png", "token")

        assert result is None

    def test_returns_none_for_non_image_content_type(self):
        mock_response = MagicMock()
        mock_response.content = b"<html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()
        mock_session = self._mock_session(response=mock_response)

        with patch(
            "firetower.slack_app.handlers.dumpslack.requests.Session",
            return_value=mock_session,
        ):
            result = _download_image("https://example.com/page", "token")

        assert result is None


class TestTriggerSlackDump:
    def test_posts_guidance_and_skips_notion_for_private_incident(self):
        client = MagicMock()
        mock_incident = MagicMock()
        mock_incident.is_private = True
        with patch(
            "firetower.slack_app.handlers.dumpslack.NotionService.from_settings",
        ) as mock_notion:
            _trigger_slack_dump(client, "C123", mock_incident)

        mock_notion.assert_not_called()
        client.chat_postMessage.assert_called_once()
        posted = client.chat_postMessage.call_args[1]["text"]
        assert "private" in posted.lower()
        assert "C123" == client.chat_postMessage.call_args[1]["channel"]

    def test_skips_silently_when_notion_not_configured(self):
        client = MagicMock()
        mock_incident = MagicMock(is_private=False)
        with patch(
            "firetower.slack_app.handlers.dumpslack.NotionService.from_settings",
            return_value=None,
        ):
            _trigger_slack_dump(client, "C123", mock_incident)

        client.chat_postMessage.assert_not_called()

    def test_posts_start_message_and_completion(self):
        client = MagicMock()
        mock_incident = MagicMock(is_private=False)
        mock_incident.captain = None
        mock_page = {"id": "page-id", "url": "https://notion.so/page-id"}
        mock_notion_link = MagicMock(url="")
        mock_notion = MagicMock()
        mock_notion.create_postmortem_page.return_value = mock_page
        with (
            patch(
                "firetower.slack_app.handlers.dumpslack.NotionService.from_settings",
                return_value=mock_notion,
            ),
            patch(
                "firetower.slack_app.handlers.dumpslack._get_channel_messages",
                return_value=[],
            ),
            patch("firetower.slack_app.handlers.dumpslack.ExternalLink") as mock_el,
            patch("firetower.slack_app.handlers.dumpslack.transaction"),
            patch("firetower.slack_app.handlers.dumpslack.settings") as mock_settings,
        ):
            mock_settings.FIRETOWER_BASE_URL = "https://firetower.example.com"
            mock_el.objects.select_for_update.return_value.get_or_create.return_value = (
                mock_notion_link,
                True,
            )
            mock_el.objects.select_for_update.return_value.get.return_value = (
                mock_notion_link
            )
            _trigger_slack_dump(client, "C123", mock_incident)

        assert client.chat_postMessage.call_count == 1
        completion_text = client.chat_postMessage.call_args_list[0][1]["text"]
        assert "notion.so/page-id" in completion_text

    def test_chat_post_message_failure_does_not_raise(self):
        client = MagicMock()
        client.chat_postMessage.side_effect = SlackApiError(
            message="not_in_channel", response={"ok": False, "error": "not_in_channel"}
        )
        mock_incident = MagicMock(is_private=False)
        mock_incident.captain = None
        mock_page = {"id": "page-id", "url": "https://notion.so/page-id"}
        mock_notion_link = MagicMock(url="")
        mock_notion = MagicMock()
        mock_notion.create_postmortem_page.return_value = mock_page
        with (
            patch(
                "firetower.slack_app.handlers.dumpslack.NotionService.from_settings",
                return_value=mock_notion,
            ),
            patch(
                "firetower.slack_app.handlers.dumpslack._get_channel_messages",
                return_value=[],
            ),
            patch("firetower.slack_app.handlers.dumpslack.ExternalLink") as mock_el,
            patch("firetower.slack_app.handlers.dumpslack.transaction"),
            patch("firetower.slack_app.handlers.dumpslack.settings") as mock_settings,
        ):
            mock_settings.FIRETOWER_BASE_URL = "https://firetower.example.com"
            mock_el.objects.select_for_update.return_value.get_or_create.return_value = (
                mock_notion_link,
                True,
            )
            mock_el.objects.select_for_update.return_value.get.return_value = (
                mock_notion_link
            )
            _trigger_slack_dump(client, "C123", mock_incident)

        client.chat_postMessage.assert_called()

    def test_waits_for_in_progress_postmortem_doc(self):
        notion_url = "https://notion.so/12345678-1234-1234-1234-123456789abc"
        client = MagicMock()
        mock_incident = MagicMock(is_private=False)
        mock_incident.captain = None
        mock_notion_link = MagicMock(url="")
        mock_notion = MagicMock()
        call_count = 0

        def simulate_url_appearing():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                mock_notion_link.url = notion_url

        mock_notion_link.refresh_from_db = simulate_url_appearing

        with (
            patch(
                "firetower.slack_app.handlers.dumpslack.NotionService.from_settings",
                return_value=mock_notion,
            ),
            patch(
                "firetower.slack_app.handlers.dumpslack._get_channel_messages",
                return_value=[],
            ),
            patch("firetower.slack_app.handlers.dumpslack.ExternalLink") as mock_el,
            patch("firetower.slack_app.handlers.dumpslack.transaction"),
            patch("firetower.slack_app.handlers.dumpslack.time") as mock_time,
        ):
            mock_el.objects.select_for_update.return_value.get_or_create.return_value = (
                mock_notion_link,
                False,
            )
            _trigger_slack_dump(client, "C123", mock_incident)

        mock_notion.create_postmortem_page.assert_not_called()
        mock_time.sleep.assert_called()
        assert client.chat_postMessage.call_count == 1
        posted = client.chat_postMessage.call_args[1]["text"]
        assert notion_url in posted

    def test_times_out_waiting_and_takes_over_orphaned_placeholder(self):
        client = MagicMock()
        mock_incident = MagicMock(is_private=False)
        mock_incident.captain = None
        mock_notion_link = MagicMock(url="")
        mock_notion = MagicMock()
        mock_page = {"id": "page-id", "url": "https://notion.so/page-id"}
        mock_notion.create_postmortem_page.return_value = mock_page

        with (
            patch(
                "firetower.slack_app.handlers.dumpslack.NotionService.from_settings",
                return_value=mock_notion,
            ),
            patch(
                "firetower.slack_app.handlers.dumpslack._get_channel_messages",
                return_value=[],
            ),
            patch("firetower.slack_app.handlers.dumpslack.ExternalLink") as mock_el,
            patch("firetower.slack_app.handlers.dumpslack.transaction"),
            patch("firetower.slack_app.handlers.dumpslack.time") as mock_time,
            patch("firetower.slack_app.handlers.dumpslack.settings") as mock_settings,
        ):
            mock_settings.FIRETOWER_BASE_URL = "https://firetower.example.com"
            mock_el.objects.select_for_update.return_value.get_or_create.return_value = (
                mock_notion_link,
                False,
            )
            mock_el.objects.select_for_update.return_value.get.return_value = (
                mock_notion_link
            )
            _trigger_slack_dump(client, "C123", mock_incident)

        assert mock_time.sleep.call_count == 15
        mock_notion.create_postmortem_page.assert_called_once()

    def test_recovers_when_placeholder_deleted_during_poll(self):
        client = MagicMock()
        mock_incident = MagicMock(is_private=False)
        mock_incident.captain = None
        mock_notion_link = MagicMock(url="")
        fresh_notion_link = MagicMock(url="")
        mock_notion = MagicMock()
        mock_page = {"id": "page-id", "url": "https://notion.so/page-id"}
        mock_notion.create_postmortem_page.return_value = mock_page

        with (
            patch(
                "firetower.slack_app.handlers.dumpslack.NotionService.from_settings",
                return_value=mock_notion,
            ),
            patch(
                "firetower.slack_app.handlers.dumpslack._get_channel_messages",
                return_value=[],
            ),
            patch("firetower.slack_app.handlers.dumpslack.ExternalLink") as mock_el,
            patch("firetower.slack_app.handlers.dumpslack.transaction"),
            patch("firetower.slack_app.handlers.dumpslack.time") as mock_time,
            patch("firetower.slack_app.handlers.dumpslack.settings") as mock_settings,
        ):
            mock_settings.FIRETOWER_BASE_URL = "https://firetower.example.com"
            mock_el.DoesNotExist = type("DoesNotExist", (Exception,), {})
            mock_notion_link.refresh_from_db.side_effect = mock_el.DoesNotExist
            mock_el.objects.select_for_update.return_value.get_or_create.side_effect = [
                (mock_notion_link, False),
                (fresh_notion_link, True),
            ]
            mock_el.objects.select_for_update.return_value.get.return_value = (
                fresh_notion_link
            )
            _trigger_slack_dump(client, "C123", mock_incident)

        mock_time.sleep.assert_called_once()
        mock_notion.create_postmortem_page.assert_called_once()

    def test_uses_existing_url_and_updates_slack(self):
        existing_url = "https://notion.so/12345678-1234-1234-1234-123456789abc"
        client = MagicMock()
        mock_incident = MagicMock(is_private=False)
        mock_incident.captain = None
        mock_notion_link = MagicMock(url=existing_url)
        mock_notion = MagicMock()
        mock_slack_service = MagicMock()
        mock_slack_service.client.bookmarks_list.return_value = {"bookmarks": []}

        with (
            patch(
                "firetower.slack_app.handlers.dumpslack.NotionService.from_settings",
                return_value=mock_notion,
            ),
            patch(
                "firetower.slack_app.handlers.dumpslack._get_channel_messages",
                return_value=[],
            ),
            patch("firetower.slack_app.handlers.dumpslack.ExternalLink") as mock_el,
            patch("firetower.slack_app.handlers.dumpslack.transaction"),
            patch(
                "firetower.slack_app.handlers.dumpslack.SlackService",
                return_value=mock_slack_service,
            ),
        ):
            mock_el.objects.select_for_update.return_value.get_or_create.return_value = (
                mock_notion_link,
                False,
            )
            _trigger_slack_dump(client, "C123", mock_incident)

        mock_notion.create_postmortem_page.assert_not_called()
        mock_notion.apply_template.assert_called_once()
        call_args = mock_notion.apply_template.call_args
        assert call_args[0][0] == "12345678-1234-1234-1234-123456789abc"
        assert call_args[1]["incident"] == mock_incident
        mock_slack_service.add_bookmark.assert_called_once_with(
            "C123", "Postmortem Doc", existing_url
        )
        posted = client.chat_postMessage.call_args[1]["text"]
        assert "Updated" in posted
        assert existing_url in posted

    def test_skips_bookmark_when_already_exists(self):
        existing_url = "https://notion.so/12345678-1234-1234-1234-123456789abc"
        client = MagicMock()
        mock_incident = MagicMock(is_private=False)
        mock_incident.captain = None
        mock_notion_link = MagicMock(url=existing_url)
        mock_notion = MagicMock()
        mock_slack_service = MagicMock()
        mock_slack_service.client.bookmarks_list.return_value = {
            "bookmarks": [{"title": "Postmortem Doc", "link": existing_url}]
        }

        with (
            patch(
                "firetower.slack_app.handlers.dumpslack.NotionService.from_settings",
                return_value=mock_notion,
            ),
            patch(
                "firetower.slack_app.handlers.dumpslack._get_channel_messages",
                return_value=[],
            ),
            patch("firetower.slack_app.handlers.dumpslack.ExternalLink") as mock_el,
            patch("firetower.slack_app.handlers.dumpslack.transaction"),
            patch(
                "firetower.slack_app.handlers.dumpslack.SlackService",
                return_value=mock_slack_service,
            ),
        ):
            mock_el.objects.select_for_update.return_value.get_or_create.return_value = (
                mock_notion_link,
                False,
            )
            _trigger_slack_dump(client, "C123", mock_incident)

        mock_slack_service.add_bookmark.assert_not_called()

    def test_race_loser_adopts_winner_page_and_archives_orphan(self):
        winner_url = "https://notion.so/12345678-1234-1234-1234-123456789abc"
        client = MagicMock()
        mock_incident = MagicMock(is_private=False)
        mock_incident.captain = None
        mock_page = {"id": "our-page", "url": "https://notion.so/our-page-id"}
        mock_notion_link = MagicMock(url="")
        winner_link = MagicMock(url=winner_url)
        mock_notion = MagicMock()
        mock_notion.create_postmortem_page.return_value = mock_page

        with (
            patch(
                "firetower.slack_app.handlers.dumpslack.NotionService.from_settings",
                return_value=mock_notion,
            ),
            patch(
                "firetower.slack_app.handlers.dumpslack._get_channel_messages",
                return_value=[],
            ),
            patch("firetower.slack_app.handlers.dumpslack.ExternalLink") as mock_el,
            patch("firetower.slack_app.handlers.dumpslack.transaction"),
            patch("firetower.slack_app.handlers.dumpslack.settings") as mock_settings,
        ):
            mock_settings.FIRETOWER_BASE_URL = "https://firetower.example.com"
            mock_el.objects.select_for_update.return_value.get_or_create.return_value = (
                mock_notion_link,
                True,
            )
            mock_el.objects.select_for_update.return_value.get.return_value = (
                winner_link
            )
            _trigger_slack_dump(client, "C123", mock_incident)

        mock_notion.archive_page.assert_called_once_with("our-page")
        mock_notion.apply_template.assert_called_once()
        call_args = mock_notion.apply_template.call_args
        assert call_args[0][0] == "12345678-1234-1234-1234-123456789abc"
        assert call_args[1]["incident"] == mock_incident
        posted = client.chat_postMessage.call_args[1]["text"]
        assert winner_url in posted

    def test_cleans_up_placeholder_on_failure(self):
        client = MagicMock()
        mock_incident = MagicMock(is_private=False)
        mock_incident.captain = None
        mock_notion_link = MagicMock(url="")
        mock_notion = MagicMock()
        mock_notion.create_postmortem_page.side_effect = RuntimeError("API error")

        with (
            patch(
                "firetower.slack_app.handlers.dumpslack.NotionService.from_settings",
                return_value=mock_notion,
            ),
            patch("firetower.slack_app.handlers.dumpslack.ExternalLink") as mock_el,
            patch("firetower.slack_app.handlers.dumpslack.transaction"),
            patch("firetower.slack_app.handlers.dumpslack.settings") as mock_settings,
        ):
            mock_settings.FIRETOWER_BASE_URL = "https://firetower.example.com"
            mock_el.objects.select_for_update.return_value.get_or_create.return_value = (
                mock_notion_link,
                True,
            )
            mock_el.objects.filter.return_value.delete.return_value = (1, {})
            _trigger_slack_dump(client, "C123", mock_incident)

        mock_el.objects.filter.assert_called_once_with(
            incident=mock_incident,
            type=ExternalLinkType.NOTION,
            url="",
        )
        mock_el.objects.filter.return_value.delete.assert_called_once()
        posted = client.chat_postMessage.call_args[1]["text"]
        assert "Failed" in posted


class TestHandleDumpslackCommand:
    def _make_args(self, notion_config=None, channel_id="C123"):
        ack = MagicMock()
        respond = MagicMock()
        client = MagicMock()
        body = {"channel_id": channel_id}
        command = {"command": "/ft"}
        return ack, body, command, client, respond, notion_config

    def test_responds_when_notion_not_configured(self):
        ack, body, command, client, respond, _ = self._make_args()
        with patch(
            "firetower.slack_app.handlers.dumpslack.NotionService.is_configured",
            return_value=False,
        ):
            handle_dumpslack_command(ack, body, command, client, respond)

        ack.assert_called_once()
        respond.assert_called_once()
        assert "not configured" in respond.call_args[0][0]

    def test_responds_when_no_channel_id(self):
        ack, body, command, client, respond, _ = self._make_args(channel_id="")
        with patch(
            "firetower.slack_app.handlers.dumpslack.NotionService.is_configured",
            return_value=True,
        ):
            handle_dumpslack_command(ack, body, command, client, respond)

        ack.assert_called_once()
        assert "channel" in respond.call_args[0][0].lower()

    def test_responds_when_no_incident_found(self):
        ack, body, command, client, respond, _ = self._make_args()
        with (
            patch(
                "firetower.slack_app.handlers.dumpslack.NotionService.is_configured",
                return_value=True,
            ),
            patch(
                "firetower.slack_app.handlers.dumpslack.get_incident_from_channel",
                return_value=None,
            ),
        ):
            handle_dumpslack_command(ack, body, command, client, respond)

        ack.assert_called_once()
        assert "No incident" in respond.call_args[0][0]

    def test_responds_when_private_incident(self):
        ack, body, command, client, respond, _ = self._make_args()
        mock_incident = MagicMock()
        mock_incident.is_private = True
        with (
            patch(
                "firetower.slack_app.handlers.dumpslack.NotionService.is_configured",
                return_value=True,
            ),
            patch(
                "firetower.slack_app.handlers.dumpslack.get_incident_from_channel",
                return_value=mock_incident,
            ),
            patch(
                "firetower.slack_app.handlers.dumpslack.trigger_slack_dump_async"
            ) as mock_async,
        ):
            handle_dumpslack_command(ack, body, command, client, respond)

        ack.assert_called_once()
        assert "private" in respond.call_args[0][0].lower()
        mock_async.assert_not_called()

    def test_dispatches_async_dump(self):
        ack, body, command, client, respond, _ = self._make_args()
        mock_incident = MagicMock(is_private=False)
        with (
            patch(
                "firetower.slack_app.handlers.dumpslack.NotionService.is_configured",
                return_value=True,
            ),
            patch(
                "firetower.slack_app.handlers.dumpslack.get_incident_from_channel",
                return_value=mock_incident,
            ),
            patch(
                "firetower.slack_app.handlers.dumpslack.trigger_slack_dump_async"
            ) as mock_async,
        ):
            handle_dumpslack_command(ack, body, command, client, respond)

        ack.assert_called_once()
        respond.assert_called()
        mock_async.assert_called_once_with(client, "C123", mock_incident)


@pytest.mark.django_db
class TestBackfillMilestones:
    _TIMELINE_MD = (
        "## Key Timestamps\n"
        "- Started: [2024-01-15 14:00 UTC]\n"
        "- Detected: [2024-01-15 14:05 UTC]\n"
        "- Analyzed: [2024-01-15 14:30 UTC]\n"
        "- Mitigation: [2024-01-15 15:00 UTC]\n"
        "- Resolution: [2024-01-15 16:00 UTC]\n"
    )

    @pytest.fixture(autouse=True)
    def disable_hooks(self, settings):
        settings.HOOKS_ENABLED = False

    def _create_incident(self, **kwargs):
        defaults = {
            "title": "Test incident",
            "severity": IncidentSeverity.P1,
            "captain": User.objects.get_or_create(
                username="captain@example.com",
                defaults={"email": "captain@example.com"},
            )[0],
            "reporter": User.objects.get_or_create(
                username="reporter@example.com",
                defaults={"email": "reporter@example.com"},
            )[0],
        }
        defaults.update(kwargs)
        return Incident.objects.create(**defaults)

    def test_sets_empty_fields(self):
        incident = self._create_incident()

        _backfill_milestones(incident, self._TIMELINE_MD)

        incident.refresh_from_db()
        assert incident.time_started == datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        assert incident.time_detected == datetime(2024, 1, 15, 14, 5, tzinfo=UTC)
        assert incident.time_analyzed == datetime(2024, 1, 15, 14, 30, tzinfo=UTC)
        assert incident.time_mitigated == datetime(2024, 1, 15, 15, 0, tzinfo=UTC)
        assert incident.time_recovered == datetime(2024, 1, 15, 16, 0, tzinfo=UTC)

    def test_computes_downtime(self):
        incident = self._create_incident()

        _backfill_milestones(incident, self._TIMELINE_MD)

        incident.refresh_from_db()
        assert incident.total_downtime == 120

    def test_skips_fields_that_are_not_null(self):
        existing_started = datetime(2024, 1, 15, 13, 0, tzinfo=UTC)
        existing_mitigated = datetime(2024, 1, 15, 14, 45, tzinfo=UTC)
        incident = self._create_incident(
            time_started=existing_started,
            time_mitigated=existing_mitigated,
        )

        _backfill_milestones(incident, self._TIMELINE_MD)

        incident.refresh_from_db()
        assert incident.time_started == existing_started
        assert incident.time_mitigated == existing_mitigated
        assert incident.time_detected == datetime(2024, 1, 15, 14, 5, tzinfo=UTC)
        assert incident.time_analyzed == datetime(2024, 1, 15, 14, 30, tzinfo=UTC)
        assert incident.time_recovered == datetime(2024, 1, 15, 16, 0, tzinfo=UTC)

    def test_no_update_when_all_fields_populated(self):
        incident = self._create_incident(
            time_started=datetime(2024, 1, 15, 13, 0, tzinfo=UTC),
            time_detected=datetime(2024, 1, 15, 13, 5, tzinfo=UTC),
            time_analyzed=datetime(2024, 1, 15, 13, 30, tzinfo=UTC),
            time_mitigated=datetime(2024, 1, 15, 14, 0, tzinfo=UTC),
            time_recovered=datetime(2024, 1, 15, 15, 0, tzinfo=UTC),
            total_downtime=120,
        )

        _backfill_milestones(incident, self._TIMELINE_MD)

        incident.refresh_from_db()
        assert incident.time_started == datetime(2024, 1, 15, 13, 0, tzinfo=UTC)
        assert incident.total_downtime == 120

    def test_no_update_when_no_timestamps_parsed(self):
        incident = self._create_incident()

        _backfill_milestones(incident, "## Timeline\n- some event\n")

        incident.refresh_from_db()
        assert incident.time_started is None
        assert incident.total_downtime is None

    def test_exception_does_not_propagate(self):
        incident = self._create_incident()

        with patch(
            "firetower.slack_app.handlers.dumpslack.IncidentWriteSerializer"
        ) as mock_cls:
            mock_cls.return_value.is_valid.return_value = True
            mock_cls.return_value.save.side_effect = RuntimeError("db error")
            _backfill_milestones(incident, self._TIMELINE_MD)
