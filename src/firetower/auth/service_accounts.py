from django.conf import settings
from django.contrib.auth.models import User


def is_read_only_non_private_service_account(user: User) -> bool:
    return user.email in settings.READ_ONLY_NON_PRIVATE_SERVICE_ACCOUNTS
