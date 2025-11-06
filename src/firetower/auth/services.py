import logging

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.integrations.services import SlackService

logger = logging.getLogger(__name__)
_slack_service = SlackService()


def sync_user_profile_from_slack(user: User) -> bool:
    """
    Sync a user's profile (name, avatar, Slack ID) from Slack.

    Args:
        user: User instance to sync

    Returns:
        True if profile was updated, False otherwise
    """
    if not user.email:
        logger.warning(f"Cannot sync user {user.username} - no email address")
        return False

    slack_profile = _slack_service.get_user_profile_by_email(user.email)

    if not slack_profile:
        logger.info(f"No Slack profile found for {user.email}")
        return False

    slack_user_id = slack_profile.get("slack_user_id", "")
    first_name = slack_profile.get("first_name", "")
    last_name = slack_profile.get("last_name", "")
    avatar_url = slack_profile.get("avatar_url", "")

    needs_save = False
    if first_name and user.first_name != first_name[:150]:
        user.first_name = first_name[:150]
        needs_save = True
    if last_name and user.last_name != last_name[:150]:
        user.last_name = last_name[:150]
        needs_save = True

    if needs_save:
        user.save()
        logger.info(f"Updated profile from Slack for {user.email}")

    if avatar_url and hasattr(user, "userprofile"):
        profile = user.userprofile
        if profile.avatar_url != avatar_url:
            try:
                URLValidator(schemes=["https"])(avatar_url)
                profile.avatar_url = avatar_url
                profile.save()
                logger.info(f"Updated avatar for user {user.email}")
                needs_save = True
            except ValidationError:
                logger.warning(f"Invalid or insecure avatar URL: {avatar_url}")

    if slack_user_id:
        external_profile, created = ExternalProfile.objects.get_or_create(
            user=user,
            type=ExternalProfileType.SLACK,
            defaults={"external_id": slack_user_id},
        )
        if not created and external_profile.external_id != slack_user_id:
            external_profile.external_id = slack_user_id
            external_profile.save()
            logger.info(f"Updated Slack ID for user {user.email}")
            needs_save = True
        elif created:
            logger.info(f"Created Slack ExternalProfile for user {user.email}")
            needs_save = True

    return needs_save


def get_or_create_user_from_iap(iap_user_id: str, email: str) -> User:
    """
    Get or create a Django user from IAP authentication.

    Args:
        iap_user_id: IAP subject ID from token (stable Google account identifier)
        email: User's email from IAP token

    Returns:
        User instance

    Raises:
        ValueError: If email or iap_user_id is missing

    Note:
        Name and avatar are fetched from Slack only on user creation.
        Use the "Sync with Slack" admin action to update existing users.
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

        # Fetch profile from Slack on user creation only
        sync_user_profile_from_slack(user)
    else:
        # For existing users, only update email if changed
        if user.email != email:
            logger.info(
                f"Updated email for user {iap_user_id}: {user.email} -> {email}"
            )
            user.email = email
            user.save()

    return user
