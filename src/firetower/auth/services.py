import logging

from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


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
    else:
        # Update email if changed
        if user.email != email:
            logger.info(
                f"Updated email for user {iap_user_id}: {user.email} -> {email}"
            )
            user.email = email
            user.save()

    # Update avatar if changed
    # UserProfile is created automatically by django signal
    if avatar_url and hasattr(user, "userprofile"):
        profile = user.userprofile
        if profile.avatar_url != avatar_url:
            logger.debug(f"Updated avatar for user {email}")
            profile.avatar_url = avatar_url
            profile.save()

    return user
