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


@pytest.mark.django_db
class TestUserListView:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="auth@example.com",
            email="auth@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

    def test_list_returns_users_alphabetically(self):
        User.objects.create_user(
            username="charlie@example.com",
            email="charlie@example.com",
            first_name="Charlie",
            last_name="Zoo",
        )
        User.objects.create_user(
            username="alice@example.com",
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
        )
        User.objects.create_user(
            username="bob@example.com",
            email="bob@example.com",
            first_name="Bob",
            last_name="Jones",
        )

        response = self.client.get("/api/users/")

        assert response.status_code == 200
        emails = [u["email"] for u in response.data["results"]]
        assert emails == sorted(emails)

    def test_pagination_structure(self):
        response = self.client.get("/api/users/")

        assert response.status_code == 200
        assert "count" in response.data
        assert "results" in response.data
        assert "next" in response.data
        assert "previous" in response.data

    def test_search_filters_by_name(self):
        User.objects.create_user(
            username="alice@example.com",
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
        )
        User.objects.create_user(
            username="bob@example.com",
            email="bob@example.com",
            first_name="Bob",
            last_name="Jones",
        )

        response = self.client.get("/api/users/?search=alice")

        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "Alice Smith"

    def test_search_filters_by_email(self):
        User.objects.create_user(
            username="alice@special.com",
            email="alice@special.com",
            first_name="Alice",
        )

        response = self.client.get("/api/users/?search=special")

        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["email"] == "alice@special.com"

    def test_search_filters_by_full_name(self):
        User.objects.create_user(
            username="alice@example.com",
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
        )

        response = self.client.get("/api/users/?search=Alice Smith")

        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "Alice Smith"

    @override_settings(IAP_ENABLED=True)
    def test_requires_authentication(self):
        client = APIClient()
        response = client.get("/api/users/")

        assert response.status_code == 403
