import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from firetower.auth.models import UserProfile


@pytest.mark.django_db
class TestCurrentUserView:
    def setup_method(self):
        """Set up test client and common test data"""
        self.client = APIClient()

    def test_current_user_returns_name_and_avatar(self):
        """Test GET /api/ui/users/me/ returns current user data"""
        user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            password="testpass123",
        )
        UserProfile.objects.create(
            user=user, avatar_url="https://example.com/avatar.jpg"
        )

        self.client.force_authenticate(user=user)
        response = self.client.get("/api/ui/users/me/")

        assert response.status_code == 200
        assert response.data["name"] == "John Doe"
        assert response.data["avatar_url"] == "https://example.com/avatar.jpg"

    def test_current_user_without_profile(self):
        """Test endpoint works when user has no UserProfile"""
        user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            first_name="Jane",
            last_name="Smith",
            password="testpass123",
        )

        self.client.force_authenticate(user=user)
        response = self.client.get("/api/ui/users/me/")

        assert response.status_code == 200
        assert response.data["name"] == "Jane Smith"
        assert response.data["avatar_url"] is None

    def test_current_user_falls_back_to_email(self):
        """Test name falls back to email when first/last name not set"""
        user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            password="testpass123",
        )

        self.client.force_authenticate(user=user)
        response = self.client.get("/api/ui/users/me/")

        assert response.status_code == 200
        assert response.data["name"] == "test@example.com"

    def test_current_user_requires_authentication(self):
        """Test endpoint requires authentication"""
        response = self.client.get("/api/ui/users/me/")

        assert response.status_code == 403

    def test_current_user_empty_avatar_url(self):
        """Test endpoint handles empty avatar_url"""
        user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            first_name="Bob",
            last_name="Jones",
            password="testpass123",
        )
        UserProfile.objects.create(user=user, avatar_url="")

        self.client.force_authenticate(user=user)
        response = self.client.get("/api/ui/users/me/")

        assert response.status_code == 200
        assert response.data["name"] == "Bob Jones"
        assert response.data["avatar_url"] is None
