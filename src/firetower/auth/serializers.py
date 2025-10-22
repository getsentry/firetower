from django.contrib.auth.models import User
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    """
    Basic User serializer for nested representations.

    Minimal user info for API responses: name and avatar only.
    """

    name = serializers.SerializerMethodField()
    avatar_url = serializers.CharField(source="userprofile.avatar_url", read_only=True)

    class Meta:
        model = User
        fields = ["name", "avatar_url"]
        read_only_fields = []

    def get_name(self, obj):
        """Get user's full name or email as fallback"""
        return obj.get_full_name() or obj.email
