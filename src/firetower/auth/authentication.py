from rest_framework.authentication import BaseAuthentication
from rest_framework.request import Request


class IAPAuthentication(BaseAuthentication):
    """
    DRF authentication class that uses the user set by IAPAuthenticationMiddleware.

    DRF's Request object has its own user property that ignores Django's request.user.
    This class bridges the gap by returning the user that our middleware already set.
    """

    def authenticate(self, request: Request) -> tuple | None:
        # Get the user from the underlying Django request (set by IAPAuthenticationMiddleware)
        django_request = request._request
        user = getattr(django_request, "user", None)

        if user and user.is_authenticated:
            return (user, None)

        return None
