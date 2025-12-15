from django.apps import AppConfig


class IncidentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "firetower.incidents"

    def ready(self):
        # Load migration logging signals
        import firetower.incidents.metrics.migrations  # noqa: F401, PLC0415
