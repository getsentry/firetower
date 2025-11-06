from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.auth.services import sync_user_profile_from_slack


@pytest.mark.django_db
class TestSyncUserProfileFromSlack:
    def test_sync_creates_external_profile(self):
        user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
        )

        mock_slack_profile = {
            "slack_user_id": "U12345",
            "first_name": "John",
            "last_name": "Doe",
            "avatar_url": "https://example.com/avatar.jpg",
        }

        with patch(
            "firetower.auth.services._slack_service.get_user_profile_by_email"
        ) as mock_get_profile:
            mock_get_profile.return_value = mock_slack_profile

            result = sync_user_profile_from_slack(user)

            assert result is True
            assert user.first_name == "John"
            assert user.last_name == "Doe"

            external_profile = ExternalProfile.objects.get(
                user=user, type=ExternalProfileType.SLACK
            )
            assert external_profile.external_id == "U12345"

    def test_sync_updates_existing_external_profile(self):
        user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
        )

        existing_profile = ExternalProfile.objects.create(
            user=user,
            type=ExternalProfileType.SLACK,
            external_id="U_OLD_ID",
        )

        mock_slack_profile = {
            "slack_user_id": "U_NEW_ID",
            "first_name": "John",
            "last_name": "Doe",
            "avatar_url": "https://example.com/avatar.jpg",
        }

        with patch(
            "firetower.auth.services._slack_service.get_user_profile_by_email"
        ) as mock_get_profile:
            mock_get_profile.return_value = mock_slack_profile

            result = sync_user_profile_from_slack(user)

            assert result is True

            existing_profile.refresh_from_db()
            assert existing_profile.external_id == "U_NEW_ID"

    def test_sync_without_slack_user_id(self):
        user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
        )

        mock_slack_profile = {
            "slack_user_id": "",
            "first_name": "John",
            "last_name": "Doe",
            "avatar_url": "https://example.com/avatar.jpg",
        }

        with patch(
            "firetower.auth.services._slack_service.get_user_profile_by_email"
        ) as mock_get_profile:
            mock_get_profile.return_value = mock_slack_profile

            result = sync_user_profile_from_slack(user)

            assert result is True
            assert user.first_name == "John"

            assert not ExternalProfile.objects.filter(
                user=user, type=ExternalProfileType.SLACK
            ).exists()

    def test_sync_user_not_found_in_slack(self):
        user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
        )

        with patch(
            "firetower.auth.services._slack_service.get_user_profile_by_email"
        ) as mock_get_profile:
            mock_get_profile.return_value = None

            result = sync_user_profile_from_slack(user)

            assert result is False
            assert not ExternalProfile.objects.filter(
                user=user, type=ExternalProfileType.SLACK
            ).exists()

    def test_sync_user_without_email(self):
        user = User.objects.create_user(
            username="test_user",
            email="",
        )

        result = sync_user_profile_from_slack(user)

        assert result is False
        assert not ExternalProfile.objects.filter(
            user=user, type=ExternalProfileType.SLACK
        ).exists()
