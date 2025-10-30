import logging

from django.contrib.auth import get_user_model
from django.db import OperationalError, transaction

logger = logging.getLogger(__name__)
User = get_user_model()


def set_initial_superusers():
    superuser_emails = [
        "richard.gibert@sentry.io",
        "spencer.murray@sentry.io",
        "taylor.osler@sentry.io",
    ]

    logger.info("Starting initial superuser setup...")
    logger.debug(f"Superuser emails to process: {superuser_emails}")

    try:
        with transaction.atomic():
            for email in superuser_emails:
                logger.debug(f"Processing email: {email}")
                try:
                    user = User.objects.get(email=email)
                    logger.debug(f"Found user with email {email}: {user.username}")

                    if not user.is_superuser:
                        logger.info(
                            f"Granting superuser status to {email} (username: {user.username})"
                        )
                        user.is_superuser = True
                        user.is_staff = True
                        user.save()
                        logger.info(f"Successfully granted superuser status to {email}")
                    else:
                        logger.debug(f"User {email} is already a superuser")

                except User.DoesNotExist:
                    logger.debug(
                        f"User with email {email} does not exist yet - will be granted superuser on first login"
                    )
                except Exception as e:
                    logger.error(
                        f"Error processing superuser for {email}: {type(e).__name__}: {e}",
                        exc_info=True,
                    )

        logger.info("Completed initial superuser setup")

    except OperationalError as e:
        logger.warning(
            f"Database not ready during superuser setup (this is normal during migrations): {e}"
        )
    except Exception as e:
        logger.error(
            f"Unexpected error during superuser setup: {type(e).__name__}: {e}",
            exc_info=True,
        )
