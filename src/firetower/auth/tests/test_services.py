from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.auth.services import (
    get_or_create_user_from_email,
    get_or_create_user_from_slack_id,
    sync_user_profile_from_slack,
)


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


@pytest.mark.django_db
class TestGetOrCreateUserFromSlackId:
    def test_returns_existing_user(self):
        existing_user = User.objects.create_user(
            username="john@example.com",
            email="john@example.com",
        )
        ExternalProfile.objects.create(
            user=existing_user,
            type=ExternalProfileType.SLACK,
            external_id="U12345",
        )

        user = get_or_create_user_from_slack_id("U12345")

        assert user == existing_user
        assert User.objects.count() == 1

    def test_creates_new_user_with_email_as_username(self):
        mock_user_info = {
            "email": "jane@example.com",
            "first_name": "Jane",
            "last_name": "Smith",
            "avatar_url": "https://example.com/avatar.jpg",
        }

        with patch(
            "firetower.auth.services._slack_service.get_user_info"
        ) as mock_get_info:
            mock_get_info.return_value = mock_user_info

            user = get_or_create_user_from_slack_id("U67890")

            assert user is not None
            assert user.username == "jane@example.com"
            assert user.email == "jane@example.com"
            assert user.first_name == "Jane"
            assert user.last_name == "Smith"
            assert user.userprofile.avatar_url == "https://example.com/avatar.jpg"

            external_profile = ExternalProfile.objects.get(
                user=user, type=ExternalProfileType.SLACK
            )
            assert external_profile.external_id == "U67890"

    def test_attaches_slack_profile_to_existing_user(self):
        """If a user exists with matching email, attach Slack profile to them."""
        existing_user = User.objects.create_user(
            username="jane@example.com",
            email="jane@example.com",
        )

        mock_user_info = {
            "email": "jane@example.com",
            "first_name": "Jane",
            "last_name": "Smith",
            "avatar_url": "https://example.com/avatar.jpg",
        }

        with patch(
            "firetower.auth.services._slack_service.get_user_info"
        ) as mock_get_info:
            mock_get_info.return_value = mock_user_info

            user = get_or_create_user_from_slack_id("U67890")

            assert user.id == existing_user.id
            assert User.objects.count() == 1

            external_profile = ExternalProfile.objects.get(
                user=user, type=ExternalProfileType.SLACK
            )
            assert external_profile.external_id == "U67890"

    def test_returns_none_if_slack_api_fails(self):
        with patch(
            "firetower.auth.services._slack_service.get_user_info"
        ) as mock_get_info:
            mock_get_info.return_value = None

            user = get_or_create_user_from_slack_id("U99999")

            assert user is None
            assert User.objects.count() == 0

    def test_returns_none_if_no_email_in_slack(self):
        mock_user_info = {
            "email": "",
            "first_name": "NoEmail",
            "last_name": "User",
            "avatar_url": "https://example.com/avatar.jpg",
        }

        with patch(
            "firetower.auth.services._slack_service.get_user_info"
        ) as mock_get_info:
            mock_get_info.return_value = mock_user_info

            user = get_or_create_user_from_slack_id("U_NO_EMAIL")

            assert user is None
            assert User.objects.count() == 0

    def test_returns_none_if_empty_slack_id(self):
        user = get_or_create_user_from_slack_id("")

        assert user is None

    def test_handles_missing_avatar(self):
        mock_user_info = {
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "avatar_url": "",
        }

        with patch(
            "firetower.auth.services._slack_service.get_user_info"
        ) as mock_get_info:
            mock_get_info.return_value = mock_user_info

            user = get_or_create_user_from_slack_id("U_NO_AVATAR")

            assert user is not None
            assert user.userprofile.avatar_url == ""

    def test_skips_invalid_avatar_url(self):
        mock_user_info = {
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "avatar_url": "http://insecure.com/avatar.jpg",
        }

        with patch(
            "firetower.auth.services._slack_service.get_user_info"
        ) as mock_get_info:
            mock_get_info.return_value = mock_user_info

            user = get_or_create_user_from_slack_id("U_BAD_AVATAR")

            assert user is not None
            assert user.userprofile.avatar_url == ""


@pytest.mark.django_db
class TestGetOrCreateUserFromEmail:
    def test_returns_existing_user(self):
        existing_user = User.objects.create_user(
            username="john@example.com",
            email="john@example.com",
        )

        user = get_or_create_user_from_email("john@example.com")

        assert user == existing_user
        assert User.objects.count() == 1

    def test_creates_new_user_from_slack(self):
        mock_slack_profile = {
            "slack_user_id": "U12345",
            "first_name": "Jane",
            "last_name": "Smith",
            "avatar_url": "https://example.com/avatar.jpg",
        }

        with patch(
            "firetower.auth.services._slack_service.get_user_profile_by_email"
        ) as mock_get_profile:
            mock_get_profile.return_value = mock_slack_profile

            user = get_or_create_user_from_email("jane@example.com")

            assert user is not None
            assert user.username == "jane@example.com"
            assert user.email == "jane@example.com"
            assert user.first_name == "Jane"
            assert user.last_name == "Smith"
            assert user.userprofile.avatar_url == "https://example.com/avatar.jpg"

            external_profile = ExternalProfile.objects.get(
                user=user, type=ExternalProfileType.SLACK
            )
            assert external_profile.external_id == "U12345"

    def test_creates_stub_user_if_slack_lookup_fails(self):
        with patch(
            "firetower.auth.services._slack_service.get_user_profile_by_email"
        ) as mock_get_profile:
            mock_get_profile.return_value = None

            user = get_or_create_user_from_email("unknown@example.com")

            assert user is not None
            assert user.email == "unknown@example.com"
            assert user.first_name == ""
            assert user.last_name == ""
            assert User.objects.count() == 1

    def test_returns_none_if_empty_email(self):
        user = get_or_create_user_from_email("")

        assert user is None

    def test_creates_user_without_slack_id(self):
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

            user = get_or_create_user_from_email("john@example.com")

            assert user is not None
            assert user.email == "john@example.com"
            assert not ExternalProfile.objects.filter(
                user=user, type=ExternalProfileType.SLACK
            ).exists()

    def test_skips_invalid_avatar_url(self):
        mock_slack_profile = {
            "slack_user_id": "U12345",
            "first_name": "Test",
            "last_name": "User",
            "avatar_url": "http://insecure.com/avatar.jpg",
        }

        with patch(
            "firetower.auth.services._slack_service.get_user_profile_by_email"
        ) as mock_get_profile:
            mock_get_profile.return_value = mock_slack_profile

            user = get_or_create_user_from_email("test@example.com")

            assert user is not None
            assert user.userprofile.avatar_url == ""
