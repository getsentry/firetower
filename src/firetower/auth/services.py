import logging

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.db import IntegrityError

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.integrations.services import SlackService

logger = logging.getLogger(__name__)
_slack_service = SlackService()


def _get_or_create_user_by_email(
    email: str,
    first_name: str = "",
    last_name: str = "",
) -> User:
    """
    Get or create a user by email, handling race conditions.

    Args:
        email: User's email address (also used as username)
        first_name: Optional first name
        last_name: Optional last name

    Returns:
        User instance (existing or newly created)
    """
    existing = User.objects.filter(email=email).first()
    if existing:
        return existing

    try:
        user = User.objects.create(
            username=email,
            email=email,
            first_name=first_name[:150] if first_name else "",
            last_name=last_name[:150] if last_name else "",
            is_active=True,
        )
        user.set_unusable_password()
        user.save()
        return user
    except IntegrityError:
        # Race condition: another request created the user
        logger.info(f"User {email} was created by concurrent request")
        existing = User.objects.filter(email=email).first()
        if existing is None:
            raise RuntimeError(f"Failed to get or create user for {email}")
        return existing


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


def get_or_create_user_from_email(email: str) -> User | None:
    """
    Get or create a Django user from email address.

    Args:
        email: User's email address

    Returns:
        User instance or None if email is empty

    Note:
        If user doesn't exist, attempts to fetch profile from Slack.
        Creates a stub user with just the email if Slack lookup fails,
        ensuring incident creation is never blocked by Slack availability.
    """
    if not email:
        logger.warning("Cannot get/create user - no email provided")
        return None

    existing_user = User.objects.filter(email=email).first()
    if existing_user:
        return existing_user

    slack_profile = _slack_service.get_user_profile_by_email(email)

    if slack_profile:
        slack_user_id = slack_profile.get("slack_user_id", "")
        first_name = slack_profile.get("first_name", "")
        last_name = slack_profile.get("last_name", "")
        avatar_url = slack_profile.get("avatar_url", "")
        logger.info(f"Creating user from Slack profile: {email}")
    else:
        logger.info(f"Could not find Slack profile for {email}, creating stub user")
        slack_user_id = ""
        first_name = ""
        last_name = ""
        avatar_url = ""

    user = _get_or_create_user_by_email(email, first_name, last_name)

    if avatar_url and not user.userprofile.avatar_url:
        try:
            URLValidator(schemes=["https"])(avatar_url)
            user.userprofile.avatar_url = avatar_url
            user.userprofile.save()
        except ValidationError:
            logger.warning(f"Invalid avatar URL for email {email}")

    if slack_user_id:
        ExternalProfile.objects.get_or_create(
            user=user,
            type=ExternalProfileType.SLACK,
            defaults={"external_id": slack_user_id},
        )

    return user


def get_or_create_user_from_slack_id(slack_user_id: str) -> User | None:
    """
    Get or create a Django user from Slack user ID.

    Args:
        slack_user_id: Slack user ID (e.g., U12345678)

    Returns:
        User instance or None if Slack API fails

    Note:
        - First checks if a Slack ExternalProfile exists for this ID
        - If a user with matching email already exists, attaches Slack profile to them
        - Otherwise creates a new user with email as username
    """
    if not slack_user_id:
        logger.warning("Cannot get/create user - no Slack user ID provided")
        return None

    try:
        external_profile = ExternalProfile.objects.get(
            type=ExternalProfileType.SLACK,
            external_id=slack_user_id,
        )
        logger.info(f"Found existing user for Slack ID: {slack_user_id}")
        return external_profile.user
    except ExternalProfile.DoesNotExist:
        pass

    slack_user_info = _slack_service.get_user_info(slack_user_id)

    if not slack_user_info:
        logger.warning(f"Could not fetch user info from Slack for ID: {slack_user_id}")
        return None

    email = slack_user_info.get("email", "")
    first_name = slack_user_info.get("first_name", "")
    last_name = slack_user_info.get("last_name", "")
    avatar_url = slack_user_info.get("avatar_url", "")

    if not email:
        logger.warning(f"Slack user {slack_user_id} has no email, cannot create user")
        return None

    user = _get_or_create_user_by_email(email, first_name, last_name)

    if avatar_url and not user.userprofile.avatar_url:
        try:
            URLValidator(schemes=["https"])(avatar_url)
            user.userprofile.avatar_url = avatar_url
            user.userprofile.save()
        except ValidationError:
            logger.warning(f"Invalid avatar URL for Slack user {slack_user_id}")

    ExternalProfile.objects.get_or_create(
        user=user,
        type=ExternalProfileType.SLACK,
        defaults={"external_id": slack_user_id},
    )

    logger.info(f"Provisioned user from Slack: {email} (Slack ID: {slack_user_id})")

    return user


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
        - First checks if an IAP ExternalProfile exists for this ID
        - If a user with matching email already exists, attaches IAP profile to them
        - Otherwise creates a new user with email as username
    """
    if not iap_user_id or not email:
        raise ValueError("IAP user ID and email are required for user creation")

    try:
        validate_email(email)
    except ValidationError:
        raise ValueError(f"Invalid email format: {email}")

    # Check if user already exists via IAP ExternalProfile
    try:
        iap_profile = ExternalProfile.objects.get(
            type=ExternalProfileType.IAP,
            external_id=iap_user_id,
        )
        user = iap_profile.user
        if user.email != email:
            logger.info(f"Updated email for user {email}: {user.email} -> {email}")
            user.email = email
            user.save()
        return user
    except ExternalProfile.DoesNotExist:
        pass

    user = _get_or_create_user_by_email(email)

    ExternalProfile.objects.get_or_create(
        user=user,
        type=ExternalProfileType.IAP,
        defaults={"external_id": iap_user_id},
    )

    sync_user_profile_from_slack(user)

    return user
