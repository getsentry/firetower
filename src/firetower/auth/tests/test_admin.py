"""
Tests for Django admin customizations.
"""

from unittest.mock import Mock, patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User

from firetower.auth.admin import UserAdmin


@pytest.mark.django_db
class TestUserAdminActions:
    """Test suite for UserAdmin actions."""

    @pytest.fixture
    def admin(self):
        """Create a UserAdmin instance."""
        site = AdminSite()
        return UserAdmin(User, site)

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        return Mock()

    def test_sync_with_slack_action_exists(self, admin):
        """Test that sync_with_slack action is registered."""
        assert "sync_with_slack" in admin.actions

    @patch("firetower.auth.admin.sync_user_profile_from_slack")
    def test_sync_with_slack_updates_users(self, mock_sync, admin, mock_request):
        """Test sync_with_slack action calls sync function for each user."""
        # Create test users
        user1 = User.objects.create(username="user1", email="user1@example.com")
        user2 = User.objects.create(username="user2", email="user2@example.com")
        queryset = User.objects.filter(id__in=[user1.id, user2.id])

        # Mock sync to return True (updated)
        mock_sync.return_value = True

        # Call the action
        admin.sync_with_slack(mock_request, queryset)

        # Verify sync was called for each user
        assert mock_sync.call_count == 2
        mock_sync.assert_any_call(user1)
        mock_sync.assert_any_call(user2)

    @patch("firetower.auth.admin.sync_user_profile_from_slack")
    def test_sync_with_slack_reports_stats(self, mock_sync, admin, mock_request):
        """Test sync_with_slack action reports correct statistics."""
        # Create test users
        user1 = User.objects.create(username="user1", email="user1@example.com")
        user2 = User.objects.create(username="user2", email="user2@example.com")
        user3 = User.objects.create(username="user3", email="user3@example.com")
        queryset = User.objects.filter(id__in=[user1.id, user2.id, user3.id])

        # Mock sync to return True for 2 users, False for 1
        mock_sync.side_effect = [True, True, False]

        # Mock message_user on the admin instance
        admin.message_user = Mock()

        # Call the action
        admin.sync_with_slack(mock_request, queryset)

        # Verify message was sent
        admin.message_user.assert_called_once()
        message = admin.message_user.call_args[0][1]
        assert "3 user(s)" in message
        assert "2 updated" in message
        assert "1 skipped" in message
