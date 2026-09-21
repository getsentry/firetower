from django.contrib.auth.models import User


def is_google_service_account(user: User) -> bool:
    return user.email.endswith(".gserviceaccount.com")
