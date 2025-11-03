"""
Basic pytest tests for Slack integration service.
"""

import os
from unittest.mock import MagicMock, patch

from .services.slack import SlackService

# Set up Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "firetower.settings")

import django
from django.conf import settings

# Setup Django
django.setup()


class TestSlackService:
    """Test suite for SlackService"""

    def test_initialization_without_bot_token(self):
        """Test that SlackService initializes without bot token but with no client."""
        mock_slack_config = {
            "BOT_TOKEN": None,
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            service = SlackService()

            # Verify the service was created but client is None
            assert service.bot_token is None
            assert service.team_id == "sentry"
            assert service.client is None

    def test_initialization_without_team_id(self):
        """Test that SlackService handles missing team_id gracefully."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": None,
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch("firetower.integrations.services.slack.WebClient"):
                service = SlackService()

                # Verify the service was created but team_id is None
                assert service.bot_token == "xoxb-test-token"
                assert service.team_id is None

                # Should return None when trying to get a URL without team_id
                url = service.get_channel_url_by_name("test-channel")
                assert url is None

    def test_initialization_with_bot_token(self):
        """Test that SlackService initializes successfully with bot token."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                service = SlackService()

                # Verify the service was created and WebClient was initialized
                assert service.bot_token == "xoxb-test-token"
                assert service.team_id == "sentry"
                assert service.client is not None
                mock_client.assert_called_once_with(token="xoxb-test-token")

    def test_get_channel_id_by_name_without_client(self):
        """Test that _get_channel_id_by_name returns None when client is not initialized."""
        mock_slack_config = {
            "BOT_TOKEN": None,
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            service = SlackService()
            channel_id = service._get_channel_id_by_name("test-channel")

            assert channel_id is None

    def test_get_channel_id_by_name_success(self):
        """Test successful channel ID lookup by name."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the conversations_list response
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.conversations_list.return_value = {
                    "channels": [
                        {"id": "C123456", "name": "test-channel"},
                        {"id": "C789012", "name": "other-channel"},
                    ]
                }

                service = SlackService()
                channel_id = service._get_channel_id_by_name("test-channel")

                assert channel_id == "C123456"
                mock_client_instance.conversations_list.assert_called_once_with(
                    types="private_channel,public_channel"
                )

    def test_get_channel_id_by_name_not_found(self):
        """Test channel ID lookup when channel doesn't exist."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the conversations_list response
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.conversations_list.return_value = {
                    "channels": [
                        {"id": "C123456", "name": "test-channel"},
                    ]
                }

                service = SlackService()
                channel_id = service._get_channel_id_by_name("nonexistent-channel")

                assert channel_id is None

    def test_get_channel_id_by_name_api_error(self):
        """Test channel ID lookup when Slack API returns an error."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the conversations_list to raise SlackApiError
                from slack_sdk.errors import SlackApiError

                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.conversations_list.side_effect = SlackApiError(
                    message="API error", response={"error": "invalid_auth"}
                )

                service = SlackService()
                channel_id = service._get_channel_id_by_name("test-channel")

                # Should return None on error
                assert channel_id is None

    def test_build_channel_url(self):
        """Test building Slack channel URL from channel ID."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch("firetower.integrations.services.slack.WebClient"):
                service = SlackService()
                url = service._build_channel_url("C123456")

                assert url == "https://sentry.slack.com/archives/C123456"

    def test_build_channel_url_custom_team(self):
        """Test building Slack channel URL with custom team ID."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "mycompany",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch("firetower.integrations.services.slack.WebClient"):
                service = SlackService()
                url = service._build_channel_url("C123456")

                assert url == "https://mycompany.slack.com/archives/C123456"

    def test_get_channel_url_by_name_success(self):
        """Test getting full channel URL by name."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the conversations_list response
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.conversations_list.return_value = {
                    "channels": [
                        {"id": "C123456", "name": "inc-123"},
                    ]
                }

                service = SlackService()
                url = service.get_channel_url_by_name("inc-123")

                assert url == "https://sentry.slack.com/archives/C123456"

    def test_get_channel_url_by_name_not_found(self):
        """Test getting channel URL when channel doesn't exist."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the conversations_list response
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.conversations_list.return_value = {
                    "channels": [
                        {"id": "C123456", "name": "inc-123"},
                    ]
                }

                service = SlackService()
                url = service.get_channel_url_by_name("nonexistent-channel")

                assert url is None

    def test_get_user_profile_by_email_success(self):
        """Test successful user profile fetch from Slack."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch("firetower.integrations.services.slack.WebClient") as MockClient:
                mock_client = MagicMock()
                MockClient.return_value = mock_client

                mock_client.users_lookupByEmail.return_value = {
                    "user": {
                        "id": "U12345",
                        "real_name": "John Doe",
                        "profile": {
                            "display_name": "Johnny",
                            "image_512": "https://example.com/avatar.jpg",
                            "image_192": "https://example.com/avatar-192.jpg",
                        },
                    }
                }

                service = SlackService()
                profile = service.get_user_profile_by_email("john@example.com")

                assert profile is not None
                assert profile["name"] == "Johnny"
                assert profile["first_name"] == "John"
                assert profile["last_name"] == "Doe"
                assert profile["avatar_url"] == "https://example.com/avatar.jpg"

    def test_get_user_profile_by_email_not_found(self):
        """Test user profile fetch when user doesn't exist in Slack."""
        from slack_sdk.errors import SlackApiError

        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch("firetower.integrations.services.slack.WebClient") as MockClient:
                mock_client = MagicMock()
                MockClient.return_value = mock_client

                mock_response = MagicMock()
                mock_response.get.return_value = "users_not_found"
                mock_client.users_lookupByEmail.side_effect = SlackApiError(
                    "user_not_found", mock_response
                )

                service = SlackService()
                profile = service.get_user_profile_by_email("nonexistent@example.com")

                assert profile is None

    def test_get_user_profile_without_client(self):
        """Test that profile fetch returns None when Slack client not initialized."""
        mock_slack_config = {
            "BOT_TOKEN": None,
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            service = SlackService()
            profile = service.get_user_profile_by_email("test@example.com")

            assert profile is None
