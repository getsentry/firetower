from django.apps import AppConfig


class AuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "firetower.auth"
    label = "firetower_auth"

    def ready(self) -> None:
        # Import signals to register handlers (F401=unused-import, PLC0415=import-outside-toplevel)
        import firetower.auth.signals  # noqa: F401, PLC0415
