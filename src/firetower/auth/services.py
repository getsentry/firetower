import logging

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email

from firetower.integrations.services import SlackService

logger = logging.getLogger(__name__)
_slack_service = SlackService()


def get_or_create_user_from_iap(
    iap_user_id: str, email: str, avatar_url: str = ""
) -> User:
    """
    Get or create a Django user from IAP authentication.

    Args:
        iap_user_id: IAP subject ID from token (stable Google account identifier)
        email: User's email from IAP token
        avatar_url: User's avatar URL from token (optional)

    Returns:
        User instance

    Raises:
        ValueError: If email or iap_user_id is missing
    """
    if not iap_user_id or not email:
        raise ValueError("IAP user ID and email are required for user creation")

    # Validate email format
    try:
        validate_email(email)
    except ValidationError:
        raise ValueError(f"Invalid email format: {email}")

    # Validate IAP user ID length (Django username field max_length is 150)
    if len(iap_user_id) > 150:
        raise ValueError(
            f"IAP user ID exceeds maximum length of 150 characters: {len(iap_user_id)}"
        )

    user, created = User.objects.get_or_create(
        username=iap_user_id,
        defaults={
            "email": email,
            "is_active": True,
        },
    )

    if created:
        user.set_unusable_password()
        user.save()
        logger.info(f"Created new user from IAP: {email} (IAP ID: {iap_user_id})")

        # Only fetch profile from Slack on user creation (not on every request)
        slack_profile = _slack_service.get_user_profile_by_email(email)

        if slack_profile:
            first_name = slack_profile.get("first_name", "")
            last_name = slack_profile.get("last_name", "")
            user.first_name = first_name[:150]
            user.last_name = last_name[:150]
            user.save()
            logger.info(f"Populated profile from Slack for {email}")

            # Use avatar from Slack profile if available and not provided via IAP
            if not avatar_url and slack_profile.get("avatar_url"):
                avatar_url = slack_profile["avatar_url"]
    else:
        # For existing users, only update email if changed
        if user.email != email:
            logger.info(
                f"Updated email for user {iap_user_id}: {user.email} -> {email}"
            )
            user.email = email
            user.save()

    # Validate avatar URL if provided (HTTPS only for security)
    if avatar_url:
        try:
            URLValidator(schemes=["https"])(avatar_url)
        except ValidationError:
            logger.warning(f"Invalid or insecure avatar URL provided: {avatar_url}")
            avatar_url = ""

    # Update avatar if changed
    # UserProfile is created automatically by django signal
    if avatar_url and hasattr(user, "userprofile"):
        profile = user.userprofile
        if profile.avatar_url != avatar_url:
            logger.debug(f"Updated avatar for user {email}")
            profile.avatar_url = avatar_url
            profile.save()

    return user
