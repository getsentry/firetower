import sys

from django.contrib.auth import get_user_model
from django.db import OperationalError, transaction


def set_initial_superusers():
    if "test" in sys.argv or "pytest" in sys.modules:
        return

    superuser_emails = [
        "richard.gibert@sentry.io",
        "spencer.murray@sentry.io",
        "taylor.osler@sentry.io",
    ]

    User = get_user_model()

    try:
        with transaction.atomic():
            for email in superuser_emails:
                try:
                    user = User.objects.get(email=email)
                    if not user.is_superuser:
                        user.is_superuser = True
                        user.is_staff = True
                        user.save()
                except User.DoesNotExist:
                    pass
    except OperationalError:
        pass
