from django.apps import AppConfig
from django.conf import settings


class IncidentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "firetower.incidents"

    def ready(self) -> None:
        # Load migration logging signals
        import firetower.incidents.metrics.migrations  # noqa: F401, PLC0415

        # Start the config.toml hot-reload watcher for this process. Guarded so
        # one-shot management commands and tests don't spawn watcher threads.
        if settings.CONFIG_WATCH_ENABLED:
            from firetower.config_reload import start_config_watcher  # noqa: PLC0415

            start_config_watcher()
