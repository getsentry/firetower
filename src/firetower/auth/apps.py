from django.apps import AppConfig


class AuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "firetower.auth"
    label = "firetower_auth"

    def ready(self):
        import firetower.auth.signals  # noqa: F401, PLC0415
