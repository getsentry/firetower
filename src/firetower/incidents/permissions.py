import logging
from typing import TYPE_CHECKING, Any

from rest_framework import permissions
from rest_framework.request import Request

from .models import Incident

logger = logging.getLogger(__name__)

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
        is_authed = request.user and request.user.is_authenticated
        logger.info(
            f"IsAuthenticated check: user={request.user}, "
            f"is_authenticated={is_authed}, type={type(request.user).__name__}"
        )
        return is_authed


class IncidentPermission(permissions.BasePermission):
    """
    Permission class for incident CRUD operations.

    - READ: User must have visibility to the incident (respects is_visible_to_user)
    - CREATE: Any authenticated user can create
    - UPDATE: Same as read permissions (anyone who can see can update)
    """

    def has_permission(self, request: Request, view: "APIView") -> bool:
        return request.user and request.user.is_authenticated

    def has_object_permission(
        self, request: Request, view: "APIView", obj: Any
    ) -> bool:
        if not isinstance(obj, Incident):
            return False

        user = request.user

        # READ: Check visibility
        if request.method in permissions.SAFE_METHODS:
            return obj.is_visible_to_user(user)

        # UPDATE/POST: Same as read permissions (for PATCH updates and POST actions)
        if request.method in ["PATCH", "POST"]:
            return obj.is_visible_to_user(user)

        return False
