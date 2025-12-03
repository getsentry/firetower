from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory
from google.auth import exceptions as google_auth_exceptions

from firetower.auth.middleware import IAPAuthenticationMiddleware
from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.auth.services import get_or_create_user_from_iap
from firetower.auth.validators import IAPTokenValidator


@pytest.mark.django_db
class TestGetOrCreateUserFromIAP:
    def test_creates_new_user_with_email_as_username(self):
        user = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:12345",
            email="test@example.com",
        )

        assert user.username == "test@example.com"
        assert user.email == "test@example.com"
        assert user.is_active
        assert not user.has_usable_password()

        # IAP ID stored in ExternalProfile
        iap_profile = ExternalProfile.objects.get(
            user=user, type=ExternalProfileType.IAP
        )
        assert iap_profile.external_id == "accounts.google.com:12345"

    def test_creates_user_profile_automatically(self):
        user = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:12345",
            email="test@example.com",
        )

        assert hasattr(user, "userprofile")
        assert user.userprofile.avatar_url == ""

    def test_creates_user_without_slack_profile(self):
        """Test that user creation works even if not in Slack."""
        user = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:12345",
            email="test@example.com",
        )

        # Profile is created but empty since no Slack lookup
        assert user.userprofile.avatar_url == ""
        assert user.first_name == ""
        assert user.last_name == ""

    def test_returns_existing_user_by_iap_profile(self):
        user1 = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:12345",
            email="test@example.com",
        )

        user2 = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:12345",
            email="test@example.com",
        )

        assert user1.id == user2.id
        assert User.objects.count() == 1
        assert ExternalProfile.objects.filter(type=ExternalProfileType.IAP).count() == 1

    def test_updates_email_if_changed(self):
        user = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:12345",
            email="old@example.com",
        )

        user = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:12345",
            email="new@example.com",
        )

        assert user.email == "new@example.com"

    def test_does_not_refetch_slack_on_subsequent_logins(self):
        """Test that Slack is only called on user creation, not subsequent logins."""
        # First login - user created
        user = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:12345",
            email="test@example.com",
        )

        # Second login - user already exists
        user2 = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:12345",
            email="test@example.com",
        )

        assert user.id == user2.id

    def test_raises_error_if_missing_required_fields(self):
        with pytest.raises(ValueError):
            get_or_create_user_from_iap(iap_user_id="", email="test@example.com")

        with pytest.raises(ValueError):
            get_or_create_user_from_iap(iap_user_id="123", email="")

    def test_raises_error_for_invalid_email(self):
        with pytest.raises(ValueError, match="Invalid email format"):
            get_or_create_user_from_iap(
                iap_user_id="accounts.google.com:12345",
                email="not-an-email",
            )

    def test_attaches_iap_profile_to_existing_user(self):
        """If a user exists with matching email (e.g., from Slack sync), attach IAP profile."""
        existing_user = User.objects.create_user(
            username="john@example.com",
            email="john@example.com",
            first_name="John",
            last_name="Doe",
        )
        ExternalProfile.objects.create(
            user=existing_user,
            type=ExternalProfileType.SLACK,
            external_id="U12345",
        )

        iap_user = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:67890",
            email="john@example.com",
        )

        # Same user, username unchanged
        assert iap_user.id == existing_user.id
        assert iap_user.username == "john@example.com"
        assert iap_user.first_name == "John"
        assert iap_user.last_name == "Doe"

        # Both profiles attached
        slack_profile = ExternalProfile.objects.get(
            user=iap_user, type=ExternalProfileType.SLACK
        )
        assert slack_profile.external_id == "U12345"

        iap_profile = ExternalProfile.objects.get(
            user=iap_user, type=ExternalProfileType.IAP
        )
        assert iap_profile.external_id == "accounts.google.com:67890"

        assert User.objects.count() == 1

    def test_creates_new_user_if_no_user_with_email(self):
        User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
        )

        new_user = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:67890",
            email="john@example.com",
        )

        assert new_user.username == "john@example.com"
        assert new_user.email == "john@example.com"
        assert User.objects.count() == 2

        iap_profile = ExternalProfile.objects.get(
            user=new_user, type=ExternalProfileType.IAP
        )
        assert iap_profile.external_id == "accounts.google.com:67890"

    def test_attach_preserves_user_profile_and_avatar(self):
        existing_user = User.objects.create_user(
            username="john@example.com",
            email="john@example.com",
        )
        existing_user.userprofile.avatar_url = "https://example.com/avatar.jpg"
        existing_user.userprofile.save()

        iap_user = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:67890",
            email="john@example.com",
        )

        assert iap_user.id == existing_user.id
        assert iap_user.userprofile.avatar_url == "https://example.com/avatar.jpg"


class TestIAPTokenValidator:
    def test_extract_user_info(self):
        validator = IAPTokenValidator()
        decoded_token = {
            "email": "test@example.com",
            "sub": "accounts.google.com:12345",
            "picture": "https://example.com/avatar.jpg",
        }

        user_info = validator.extract_user_info(decoded_token)

        assert user_info["email"] == "test@example.com"
        assert user_info["user_id"] == "accounts.google.com:12345"

    def test_extract_user_info_without_picture(self):
        validator = IAPTokenValidator()
        decoded_token = {
            "email": "test@example.com",
            "sub": "accounts.google.com:12345",
        }

        user_info = validator.extract_user_info(decoded_token)

        assert user_info["email"] == "test@example.com"
        assert user_info["user_id"] == "accounts.google.com:12345"

    @patch("firetower.auth.validators.id_token.verify_token")
    def test_validate_token_success(self, mock_verify):
        mock_verify.return_value = {
            "email": "test@example.com",
            "sub": "accounts.google.com:12345",
            "iss": "https://cloud.google.com/iap",
        }

        validator = IAPTokenValidator()
        decoded = validator.validate_token("fake_token")

        assert decoded["email"] == "test@example.com"
        mock_verify.assert_called_once()

    @patch("firetower.auth.validators.id_token.verify_token")
    def test_validate_token_invalid_issuer(self, mock_verify):
        mock_verify.return_value = {
            "email": "test@example.com",
            "sub": "accounts.google.com:12345",
            "iss": "https://evil.com",
        }

        validator = IAPTokenValidator()

        with pytest.raises(ValueError, match="Invalid issuer"):
            validator.validate_token("fake_token")

    @patch("firetower.auth.validators.id_token.verify_token")
    def test_validate_token_verification_fails(self, mock_verify):
        mock_verify.side_effect = google_auth_exceptions.GoogleAuthError(
            "Invalid signature"
        )

        validator = IAPTokenValidator()

        with pytest.raises(ValueError, match="Invalid IAP token"):
            validator.validate_token("fake_token")


@pytest.mark.django_db
class TestIAPAuthenticationMiddleware:
    @pytest.fixture
    def factory(self):
        return RequestFactory()

    @pytest.fixture
    def get_response(self):
        return Mock()

    @patch("firetower.auth.middleware.settings.IAP_ENABLED", True)
    @patch.object(IAPTokenValidator, "validate_token")
    @patch.object(IAPTokenValidator, "extract_user_info")
    def test_authenticates_valid_iap_token(
        self, mock_extract, mock_validate, factory, get_response
    ):
        mock_validate.return_value = {"email": "test@example.com", "sub": "12345"}
        mock_extract.return_value = {
            "email": "test@example.com",
            "user_id": "accounts.google.com:12345",
        }

        middleware = IAPAuthenticationMiddleware(get_response)
        request = factory.get("/")
        request.META["HTTP_X_GOOG_IAP_JWT_ASSERTION"] = "valid_token"

        middleware(request)

        assert request.user.is_authenticated
        assert request.user.email == "test@example.com"

    @patch("firetower.auth.middleware.settings.IAP_ENABLED", True)
    def test_sets_anonymous_user_when_token_missing(self, factory, get_response):
        middleware = IAPAuthenticationMiddleware(get_response)
        request = factory.get("/")

        middleware(request)

        assert isinstance(request.user, AnonymousUser)

    @patch("firetower.auth.middleware.settings.IAP_ENABLED", True)
    @patch.object(IAPTokenValidator, "validate_token")
    def test_sets_anonymous_user_when_token_invalid(
        self, mock_validate, factory, get_response
    ):
        mock_validate.side_effect = ValueError("Invalid token")

        middleware = IAPAuthenticationMiddleware(get_response)
        request = factory.get("/")
        request.META["HTTP_X_GOOG_IAP_JWT_ASSERTION"] = "invalid_token"

        middleware(request)

        assert isinstance(request.user, AnonymousUser)

    @patch("firetower.auth.middleware.settings.IAP_ENABLED", False)
    def test_dev_mode_creates_dev_user(self, factory, get_response):
        middleware = IAPAuthenticationMiddleware(get_response)
        request = factory.get("/")

        middleware(request)

        assert request.user.is_authenticated
        assert request.user.username == "dev_user"
        assert request.user.is_superuser
        assert request.user.is_staff

    @patch("firetower.auth.middleware.settings.IAP_ENABLED", False)
    def test_dev_mode_reuses_existing_dev_user(self, factory, get_response):
        User.objects.create(
            username="dev_user",
            email="dev@example.com",
            is_superuser=True,
            is_staff=True,
        )

        middleware = IAPAuthenticationMiddleware(get_response)
        request = factory.get("/")

        middleware(request)

        assert User.objects.filter(username="dev_user").count() == 1
