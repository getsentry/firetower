import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

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

    def __init__(self, get_response):
        self.get_response = get_response
        self.validator = IAPTokenValidator() if settings.IAP_ENABLED else None

        if settings.IAP_ENABLED:
            logger.info("IAP authentication enabled")
        else:
            logger.info("IAP authentication disabled - using dev mode")

    def __call__(self, request):
        if settings.IAP_ENABLED:
            self._authenticate_iap(request)
        else:
            self._authenticate_dev(request)

        return self.get_response(request)

    def _authenticate_iap(self, request):
        """Authenticate via IAP token validation."""
        token = request.META.get(self.IAP_HEADER)

        if not token:
            logger.warning("IAP token missing from request")
            request.user = AnonymousUser()
            return

        try:
            decoded_token = self.validator.validate_token(token)
            user_info = self.validator.extract_user_info(decoded_token)

            user = get_or_create_user_from_iap(
                iap_user_id=user_info["user_id"],
                email=user_info["email"],
                avatar_url=user_info.get("avatar_url", ""),
            )

            request.user = user
            logger.debug(
                f"IAP authentication successful for user {user.email} (ID: {user.username})"
            )

        except ValueError as e:
            logger.error(f"IAP authentication failed: {e}")
            request.user = AnonymousUser()

    def _authenticate_dev(self, request):
        """Development mode: bypass IAP validation."""
        import os

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
