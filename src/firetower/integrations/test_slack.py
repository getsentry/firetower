"""
Basic pytest tests for Slack integration service.
"""

import os
from unittest.mock import MagicMock, patch

from slack_sdk.errors import SlackApiError

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
                            "image_512": "https://example.com/avatar-512.jpg",
                        },
                    }
                }

                service = SlackService()
                profile = service.get_user_profile_by_email("john@example.com")

                assert profile is not None
                assert profile["slack_user_id"] == "U12345"
                assert profile["name"] == "Johnny"
                assert profile["first_name"] == "John"
                assert profile["last_name"] == "Doe"
                assert profile["avatar_url"] == "https://example.com/avatar-512.jpg"

    def test_get_user_profile_by_email_not_found(self):
        """Test user profile fetch when user doesn't exist in Slack."""
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
