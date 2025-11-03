"""
Slack integration service for fetching channel data and building URLs.

This service provides a simple interface to interact with Slack's API
and retrieve information about channels.
"""

import logging

from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


class SlackService:
    """
    Service class for interacting with Slack API.

    Provides methods to fetch channel information and build Slack URLs
    for the Firetower application.
    """

    def __init__(self):
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

    def _get_channel_id_by_name(self, channel_name: str) -> str | None:
        """
        Get Slack channel ID by name using the bot token.

        Args:
            channel_name (str): The name of the Slack channel (without the # prefix)

        Returns:
            str | None: The channel ID if found, None otherwise
        """
        if not self.client:
            logger.warning("Cannot fetch channel - Slack client not initialized")
            return None

        try:
            logger.debug(f"Fetching channel ID for: {channel_name}")
            response = self.client.conversations_list(
                types="private_channel,public_channel"
            )

            channels = response.get("channels", [])
            logger.debug(f"Found {len(channels)} channels")

            for channel in channels:
                if channel["name"] == channel_name:
                    logger.info(
                        f"Found channel {channel_name}",
                        extra={"channel_id": channel["id"]},
                    )
                    return channel["id"]

            logger.warning(f"Channel not found: {channel_name}")
        except SlackApiError as e:
            logger.error(
                f"Error fetching Slack channels: {e}",
                extra={"channel_name": channel_name},
            )

        return None

    def _build_channel_url(self, channel_id: str) -> str:
        """
        Build a Slack channel URL from a channel ID.

        Args:
            channel_id (str): The Slack channel ID

        Returns:
            str: The full Slack channel URL
        """
        # Use the team_id from settings to construct the URL
        # Format: https://{team_id}.slack.com/archives/{channel_id}
        return f"https://{self.team_id}.slack.com/archives/{channel_id}"

    def get_channel_url_by_name(self, channel_name: str) -> str | None:
        """
        Get a Slack channel URL by channel name.

        Args:
            channel_name (str): The name of the Slack channel (without the # prefix)

        Returns:
            str | None: The full Slack channel URL if found, None otherwise
        """
        if not self.team_id:
            return None
        channel_id = self._get_channel_id_by_name(channel_name)
        return self._build_channel_url(channel_id) if channel_id else None

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
            logger.debug(f"Fetching Slack profile for: {email}")
            response = self.client.users_lookupByEmail(email=email)

            user = response.get("user", {})
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

            avatar_url = profile.get(
                "image_512",
                profile.get("image_192", profile.get("image_72", "")),
            )

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
