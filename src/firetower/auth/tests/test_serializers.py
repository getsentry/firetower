import pytest
from django.contrib.auth.models import User

from firetower.auth.serializers import UserSerializer


@pytest.mark.django_db
class TestUserSerializer:
    def test_user_serialization(self):
        """Test User serialization"""
        user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

        serializer = UserSerializer(user)
        data = serializer.data

        # Minimal fields only
        assert data["name"] == "Test User"
        assert "avatar_url" in data

        # Should not include these
        assert "id" not in data
        assert "email" not in data
        assert "username" not in data
        assert "first_name" not in data
        assert "last_name" not in data

    def test_user_serialization_no_full_name(self):
        """Test User serialization when no first/last name"""
        user = User.objects.create_user(
            username="test@example.com", email="test@example.com"
        )

        serializer = UserSerializer(user)
        data = serializer.data

        assert data["name"] == "test@example.com"  # Falls back to email
