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

    def get_channel_members(self, channel_id: str) -> list[str] | None:
        """Get all members of a Slack channel."""
        if not self.client:
            return None

        try:
            response = self.client.conversations_members(channel=channel_id)
            return response.get("members", [])
        except SlackApiError as e:
            print(f"Error fetching channel members: {e}")
            return None

    def get_user_info(self, user_id: str) -> dict | None:
        """Get user information from Slack."""
        if not self.client:
            return None

        try:
            response = self.client.users_info(user=user_id)
            user = response.get("user", {})
            profile = user.get("profile", {})

            return {
                "id": user.get("id"),
                "name": user.get("name"),
                "real_name": profile.get("real_name"),
                "display_name": profile.get("display_name"),
                "avatar_url": profile.get("image_48"),
                "email": profile.get("email"),
            }
        except SlackApiError as e:
            print(f"Error fetching user info: {e}")
            return None

    def get_channel_participants(self, channel_name: str) -> list[dict]:
        """Get all participants in a channel with their full information."""
        channel_id = self._get_channel_id_by_name(channel_name)
        if not channel_id:
            return []

        member_ids = self.get_channel_members(channel_id)
        if not member_ids:
            return []

        participants = []
        for user_id in member_ids:
            user_info = self.get_user_info(user_id)
            if user_info:
                full_name = user_info.get("real_name", "").strip()
                if not full_name:
                    full_name = user_info.get("name") or ""

                participants.append(
                    {
                        "name": full_name,
                        "email": user_info.get("email"),
                        "avatar_url": user_info["avatar_url"],
                        "role": None,
                    }
                )

        return participants
