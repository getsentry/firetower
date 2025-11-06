from typing import Any

from django.conf import settings
from google.auth import exceptions as google_auth_exceptions
from google.auth.transport import requests
from google.oauth2 import id_token


class IAPTokenValidator:
    """
    Validates Google IAP JWT tokens.

    IAP places a signed JWT in the X-Goog-IAP-JWT-Assertion header.
    This validator verifies the signature and extracts user information.
    """

    IAP_ISSUER = "https://cloud.google.com/iap"

    def __init__(self) -> None:
        """Initialize the validator with audience from settings."""
        self.audience = settings.IAP_AUDIENCE

    def validate_token(self, token: str) -> dict[Any, Any] | None:
        """
        Validate an IAP JWT token and return the decoded claims.

        Args:
            token: The JWT token from X-Goog-IAP-JWT-Assertion header

        Returns:
            Dictionary containing user claims (email, sub, etc.) or None if invalid

        Raises:
            ValueError: If token validation fails
        """
        try:
            request = requests.Request()
            decoded_token = id_token.verify_token(
                token,
                request=request,
                audience=self.audience,
                certs_url="https://www.gstatic.com/iap/verify/public_key",
            )

            if decoded_token.get("iss") != self.IAP_ISSUER:
                raise ValueError(f"Invalid issuer: {decoded_token.get('iss')}")

            return decoded_token

        except (ValueError, google_auth_exceptions.GoogleAuthError) as e:
            raise ValueError(f"Invalid IAP token: {str(e)}")

    def extract_user_info(self, decoded_token: dict[Any, Any]) -> dict[str, Any]:
        """
        Extract user information from decoded token.

        Args:
            decoded_token: The decoded JWT claims

        Returns:
            Dictionary with email and user_id
        """
        return {
            "email": decoded_token.get("email"),
            "user_id": decoded_token.get("sub"),
        }
