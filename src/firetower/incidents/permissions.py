from typing import TYPE_CHECKING

from rest_framework import permissions
from rest_framework.request import Request

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
