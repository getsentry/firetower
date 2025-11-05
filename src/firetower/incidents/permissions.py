from typing import TYPE_CHECKING, Any

from rest_framework import permissions
from rest_framework.request import Request

from .models import Incident

# Prevents circular import at runtime
if TYPE_CHECKING:
    from rest_framework.views import APIView


class IsAuthenticated(permissions.BasePermission):
    """
    Require authentication for all requests.

    Behind Google IAP, this shouldn't fail, but we check explicitly
    to ensure no unauthenticated access slips through.
    """

    def has_permission(self, request: Request, view: "APIView") -> bool:
        return request.user and request.user.is_authenticated


class IncidentPermission(permissions.BasePermission):
    """
    Permission class for incident CRUD operations.

    - READ: User must have visibility to the incident (respects is_visible_to_user)
    - CREATE: Any authenticated user can create
    - UPDATE: Captain, reporter, participants, or superuser
    """

    def has_permission(self, request: Request, view: "APIView") -> bool:
        # All operations require authentication
        if not request.user or not request.user.is_authenticated:
            return False

        # CREATE is allowed for any authenticated user
        if request.method == "POST":
            return True

        # Other operations handled by has_object_permission
        return True

    def has_object_permission(
        self, request: Request, view: "APIView", obj: Any
    ) -> bool:
        if not isinstance(obj, Incident):
            return False

        user = request.user

        # READ: Check visibility
        if request.method in permissions.SAFE_METHODS:
            return obj.is_visible_to_user(user)

        # UPDATE: Captain, reporter, participants, or superuser
        if request.method in ["PUT", "PATCH"]:
            return (
                user.is_superuser
                or obj.captain == user
                or obj.reporter == user
                or obj.participants.filter(id=user.id).exists()
            )

        return False
