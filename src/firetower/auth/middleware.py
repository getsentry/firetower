import logging
import os
from collections.abc import Callable

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.middleware.csrf import CsrfViewMiddleware

from firetower.auth.services import get_or_create_user_from_iap
from firetower.auth.validators import IAPTokenValidator

logger = logging.getLogger(__name__)
User = get_user_model()


class IAPAuthenticationMiddleware:
    """
    Middleware to authenticate users via Google IAP.

    Extracts and validates the IAP JWT token from the X-Goog-IAP-JWT-Assertion header,
    then creates/retrieves the corresponding Django user.
    """

    IAP_HEADER = "HTTP_X_GOOG_IAP_JWT_ASSERTION"

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.validator = IAPTokenValidator() if settings.IAP_ENABLED else None

        if settings.IAP_ENABLED:
            logger.info("IAP authentication enabled")
        else:
            logger.info("IAP authentication disabled - using dev mode")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if settings.IAP_ENABLED:
            self._authenticate_iap(request)
        else:
            self._authenticate_dev(request)

        return self.get_response(request)

    def _authenticate_iap(self, request: HttpRequest) -> None:
        """Authenticate via IAP token validation."""
        token = request.META.get(self.IAP_HEADER)

        if not token:
            logger.warning("IAP token missing from request")
            request.user = AnonymousUser()
            return

        # Validator should always be set when IAP is enabled
        if self.validator is None:
            logger.critical(
                "IAP authentication called but validator is not initialized. "
                "Check IAP_ENABLED setting and middleware configuration."
            )
            request.user = AnonymousUser()
            return

        try:
            decoded_token = self.validator.validate_token(token)
            if decoded_token is None:
                raise ValueError("Token validation returned None")
            user_info = self.validator.extract_user_info(decoded_token)

            user = get_or_create_user_from_iap(
                iap_user_id=user_info["user_id"],
                email=user_info["email"],
            )

            request.user = user
            logger.info(f"IAP authentication successful for user {user.email}")

        except ValueError as e:
            logger.error(f"IAP authentication failed: {e}")
            request.user = AnonymousUser()
        except Exception as e:
            logger.critical(
                f"Unexpected error during IAP authentication: {type(e).__name__}: {e}",
                exc_info=True,
            )
            request.user = AnonymousUser()

    def _authenticate_dev(self, request: HttpRequest) -> None:
        """Development mode: bypass IAP validation."""
        # Sanity check: ensure we're actually in dev environment
        if os.environ.get("DJANGO_ENV", "dev") != "dev":
            logger.critical(
                "Dev authentication called in non-dev environment! Check IAP_ENABLED setting."
            )
            request.user = AnonymousUser()
            return

        # In development, allow session-based auth or create a test user
        if hasattr(request, "user") and request.user.is_authenticated:
            return

        # Create/use a test user for development
        user, _ = User.objects.get_or_create(
            username="dev_user",
            defaults={
                "email": "dev@example.com",
                "is_active": True,
                "is_superuser": True,
                "is_staff": True,
            },
        )
        request.user = user


class ConditionalCsrfViewMiddleware(CsrfViewMiddleware):
    """
    CSRF middleware that skips validation for IAP-authenticated requests.

    Since Firetower uses IAP for all authentication (not session-based auth),
    CSRF protection is not needed. Security is provided by:
    - IAP: Validates identity for all requests (browser and service)
    - CORS: Blocks cross-origin requests from malicious sites

    CSRF attacks exploit session cookies, which we don't use for auth.
    """

    def _is_iap_authenticated(self, request: HttpRequest) -> bool:
        """Check if request is authenticated via IAP."""
        return bool(request.META.get("HTTP_X_GOOG_IAP_JWT_ASSERTION"))

    def process_view(
        self,
        request: HttpRequest,
        callback: Callable,
        callback_args: tuple,
        callback_kwargs: dict,
    ) -> HttpResponseForbidden | None:
        if self._is_iap_authenticated(request):
            return None
        return super().process_view(request, callback, callback_args, callback_kwargs)
