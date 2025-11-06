from django.contrib.auth.models import User
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    """
    Basic User serializer for nested representations.

    Minimal user info for API responses: name and avatar only.
    """

    name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["name", "avatar_url"]
        read_only_fields: list[str] = []

    def get_name(self, obj: User) -> str:
        """Get user's full name or email as fallback"""
        return obj.get_full_name() or obj.email

    def get_avatar_url(self, obj: User) -> str | None:
        """Get avatar URL from userprofile if it exists"""
        try:
            return obj.userprofile.avatar_url or None
        except AttributeError:
            return None
