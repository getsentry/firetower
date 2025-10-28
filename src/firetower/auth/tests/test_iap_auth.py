from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory

from firetower.auth.middleware import IAPAuthenticationMiddleware
from firetower.auth.services import get_or_create_user_from_iap
from firetower.auth.validators import IAPTokenValidator


@pytest.mark.django_db
class TestGetOrCreateUserFromIAP:
    def test_creates_new_user_with_iap_id_as_username(self):
        user = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:12345",
            email="test@example.com",
        )

        assert user.username == "accounts.google.com:12345"
        assert user.email == "test@example.com"
        assert user.is_active
        assert not user.has_usable_password()

    def test_creates_user_profile_automatically(self):
        user = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:12345",
            email="test@example.com",
        )

        assert hasattr(user, "userprofile")
        assert user.userprofile.avatar_url == ""

    def test_creates_user_with_avatar_url(self):
        user = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:12345",
            email="test@example.com",
            avatar_url="https://example.com/avatar.jpg",
        )

        assert user.userprofile.avatar_url == "https://example.com/avatar.jpg"

    def test_returns_existing_user_by_iap_id(self):
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

    def test_updates_avatar_if_changed(self):
        user = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:12345",
            email="test@example.com",
            avatar_url="https://example.com/old.jpg",
        )

        user = get_or_create_user_from_iap(
            iap_user_id="accounts.google.com:12345",
            email="test@example.com",
            avatar_url="https://example.com/new.jpg",
        )

        assert user.userprofile.avatar_url == "https://example.com/new.jpg"

    def test_raises_error_if_missing_required_fields(self):
        with pytest.raises(ValueError):
            get_or_create_user_from_iap(iap_user_id="", email="test@example.com")

        with pytest.raises(ValueError):
            get_or_create_user_from_iap(iap_user_id="123", email="")


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
        assert user_info["avatar_url"] == "https://example.com/avatar.jpg"

    def test_extract_user_info_without_picture(self):
        validator = IAPTokenValidator()
        decoded_token = {
            "email": "test@example.com",
            "sub": "accounts.google.com:12345",
        }

        user_info = validator.extract_user_info(decoded_token)

        assert user_info["avatar_url"] == ""

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
        mock_verify.side_effect = Exception("Invalid signature")

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
            "avatar_url": "",
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
