"""
Hook for reacting to ``config.toml`` hot reloads.

``on_config_reload`` is called by ``firetower.config_reload`` after the new
configuration has been applied to Django settings. Put any extra logic that
needs to run when configuration values change here (invalidating caches,
reconnecting clients, emitting a metric, etc.).

Keep the implementation defensive: it runs inside the watcher thread, and an
exception raised here is logged but does not stop watching. The settings have
already been updated by the time this is called, so read the new values from
``django.conf.settings`` or the passed-in ``new_config``.
"""

import logging

from firetower.config import ConfigFile

logger = logging.getLogger(__name__)


def on_config_reload(old_config: ConfigFile | None, new_config: ConfigFile) -> None:
    """
    React to a configuration reload.

    Args:
        old_config: The configuration that was active before the reload, or
            ``None`` if the previous config could not be determined.
        new_config: The configuration that has just been applied to settings.

    Default implementation only logs. Extend as needed.
    """
    logger.info("Configuration reloaded; running post-reload hook")
