import hashlib
import hmac
import time

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

User = get_user_model()

SERVICE_USERNAME = "firetower-slack-app"


class SlackSigningSecretAuthentication(BaseAuthentication):
    """
    DRF authentication class that verifies Slack request signatures.

    Validates the X-Slack-Signature header using HMAC-SHA256 with the
    configured signing secret. On success, returns a service user.
    """

    MAX_TIMESTAMP_AGE_SECONDS = 120

    def authenticate(self, request: Request) -> tuple | None:
        django_request = request._request

        timestamp = django_request.META.get("HTTP_X_SLACK_REQUEST_TIMESTAMP")
        signature = django_request.META.get("HTTP_X_SLACK_SIGNATURE")

        if not timestamp or not signature:
            return None

        try:
            ts = int(timestamp)
        except ValueError:
            raise AuthenticationFailed("Invalid timestamp")

        if abs(time.time() - ts) > self.MAX_TIMESTAMP_AGE_SECONDS:
            raise AuthenticationFailed("Request timestamp too old")

        signing_secret = settings.SLACK.get("SIGNING_SECRET", "")
        raw_body = django_request.body
        sig_basestring = f"v0:{timestamp}:{raw_body.decode('utf-8')}"

        computed = (
            "v0="
            + hmac.new(
                signing_secret.encode("utf-8"),
                sig_basestring.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        )

        if not hmac.compare_digest(computed, signature):
            raise AuthenticationFailed("Invalid signature")

        user, _ = User.objects.get_or_create(
            username=SERVICE_USERNAME,
            defaults={"is_active": True},
        )

        return (user, None)
