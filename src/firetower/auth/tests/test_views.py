import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestCurrentUserView:
    def setup_method(self):
        """Set up test client and common test data"""
        self.client = APIClient()

    def test_current_user_returns_name_and_avatar(self):
        """Test GET /api/ui/users/me/ returns current user data"""
        user = User.objects.create_user(
            username="john@example.com",
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            password="testpass123",
        )
        # UserProfile is auto-created by signal, just update it
        user.userprofile.avatar_url = "https://example.com/avatar.jpg"
        user.userprofile.save()

        self.client.force_authenticate(user=user)
        response = self.client.get("/api/ui/users/me/")

        assert response.status_code == 200
        assert response.data["name"] == "John Doe"
        assert response.data["avatar_url"] == "https://example.com/avatar.jpg"

    def test_current_user_with_empty_avatar(self):
        """Test endpoint returns null for empty avatar_url"""
        user = User.objects.create_user(
            username="jane@example.com",
            email="jane@example.com",
            first_name="Jane",
            last_name="Smith",
            password="testpass123",
        )
        # UserProfile is auto-created by signal with blank avatar_url

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

    @override_settings(IAP_ENABLED=True)
    def test_current_user_requires_authentication(self):
        """Test endpoint requires authentication when IAP is enabled"""
        response = self.client.get("/api/ui/users/me/")

        assert response.status_code == 403
