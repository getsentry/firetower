"""
Slack integration service for fetching user profile data.

This service provides a simple interface to interact with Slack's API
and retrieve user profile information (name, avatar).
"""

import logging
from typing import Any

from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


class SlackService:
    """
    Service class for interacting with Slack API.

    Provides methods to fetch user profile information for authentication.
    """

    def __init__(self) -> None:
        """Initialize the Slack service."""
        slack_config = settings.SLACK

        self.bot_token = slack_config.get("BOT_TOKEN")
        self.team_id = slack_config.get("TEAM_ID")

        logger.info(
            "Initializing SlackService",
            extra={
                "has_bot_token": self.bot_token is not None,
                "team_id": self.team_id,
            },
        )

        self.client = WebClient(token=self.bot_token) if self.bot_token else None

        if self.client is None:
            logger.warning("Slack client not initialized - missing bot token")

    def get_user_profile_by_email(self, email: str) -> dict | None:
        """
        Get user profile information from Slack by email.

        Args:
            email: User's email address

        Returns:
            dict with 'name' and 'avatar_url', or None if not found
        """
        if not self.client:
            logger.warning("Cannot fetch user - Slack client not initialized")
            return None

        try:
            logger.info(f"Fetching Slack profile for: {email}")
            response = self.client.users_lookupByEmail(email=email)

            user: dict[str, Any] = response.get("user", {})
            profile = user.get("profile", {})

            real_name = user.get("real_name", "")
            display_name = profile.get("display_name", "")
            name = display_name or real_name

            first_name = ""
            last_name = ""
            if real_name:
                parts = real_name.strip().split(None, 1)
                first_name = parts[0] if len(parts) > 0 else ""
                last_name = parts[1] if len(parts) > 1 else ""

            # Get avatar - Slack provides image_512 as the smallest size
            avatar_url = profile.get("image_512", "")

            logger.info(f"Found Slack profile for {email}")
            return {
                "name": name,
                "first_name": first_name,
                "last_name": last_name,
                "avatar_url": avatar_url,
            }

        except SlackApiError as e:
            if e.response.get("error") == "users_not_found":
                logger.info(f"User not found in Slack: {email}")
            else:
                logger.error(
                    f"Error fetching Slack user profile: {e}",
                    extra={"email": email},
                )
            return None

    def parse_channel_id_from_url(self, url: str) -> str | None:
        """
        Extract Slack channel ID from URL.

        Args:
            url: Slack channel URL (e.g., https://workspace.slack.com/archives/C12345678)

        Returns:
            Channel ID (e.g., C12345678) or None if not found
        """
        if not url:
            return None

        if "/archives/" in url:
            parts = url.split("/archives/")
            if len(parts) > 1:
                channel_id = parts[1].split("/")[0].split("?")[0]
                if channel_id:
                    logger.info(f"Parsed channel ID from URL: {channel_id}")
                    return channel_id

        logger.warning(f"Could not parse channel ID from URL: {url}")
        return None

    def get_channel_members(self, channel_id: str) -> list[str] | None:
        """
        Get list of member IDs in a Slack channel.

        Args:
            channel_id: Slack channel ID (e.g., C12345678)

        Returns:
            List of Slack user IDs, or None if error
        """
        if not self.client:
            logger.warning(
                "Cannot fetch channel members - Slack client not initialized"
            )
            return None

        try:
            logger.info(f"Fetching members for channel: {channel_id}")
            response = self.client.conversations_members(channel=channel_id)
            members = response.get("members", [])
            logger.info(f"Found {len(members)} members in channel {channel_id}")
            return members

        except SlackApiError as e:
            logger.error(
                f"Error fetching channel members: {e}",
                extra={"channel_id": channel_id},
            )
            return None

    def get_user_info(self, slack_user_id: str) -> dict | None:
        """
        Get user information from Slack by user ID.

        Args:
            slack_user_id: Slack user ID (e.g., U12345678)

        Returns:
            dict with 'email', 'first_name', 'last_name', 'avatar_url', or None if not found
        """
        if not self.client:
            logger.warning("Cannot fetch user info - Slack client not initialized")
            return None

        try:
            logger.info(f"Fetching Slack user info for: {slack_user_id}")
            response = self.client.users_info(user=slack_user_id)

            user = response.get("user", {})
            profile = user.get("profile", {})

            email = profile.get("email", "")
            real_name = user.get("real_name", "")

            first_name = ""
            last_name = ""
            if real_name:
                parts = real_name.strip().split(None, 1)
                first_name = parts[0] if len(parts) > 0 else ""
                last_name = parts[1] if len(parts) > 1 else ""

            avatar_url = profile.get("image_512", "")

            logger.info(f"Found Slack user info for {slack_user_id}")
            return {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "avatar_url": avatar_url,
            }

        except SlackApiError as e:
            logger.error(
                f"Error fetching Slack user info: {e}",
                extra={"slack_user_id": slack_user_id},
            )
            return None
