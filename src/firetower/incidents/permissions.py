from typing import Any

from rest_framework import permissions


class IsAuthenticated(permissions.BasePermission):
    """
    Require authentication for all requests.

    Behind Google IAP, this shouldn't fail, but we check explicitly
    to ensure no unauthenticated access slips through.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        return request.user and request.user.is_authenticated
