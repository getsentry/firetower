from django.apps import AppConfig


class AuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "firetower.auth"
    label = "firetower_auth"

    def ready(self):
        pass
