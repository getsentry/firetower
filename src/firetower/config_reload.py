"""
Hot reload of ``config.toml`` via watchfiles.

A daemon watcher thread is started once per process (see
``firetower.incidents.apps.IncidentsConfig.ready``). Because each Django
process — every web worker, the Slack bot, each q-cluster worker — holds its
own copy of ``django.conf.settings`` in memory, the watcher must run inside
each process; a standalone process could only mutate its own settings.

When ``config.toml`` changes the watcher rebuilds the config, re-applies every
config-derived setting via ``firetower.settings.apply_config``, then invokes
``firetower.config_hooks.on_config_reload``. Failures (a malformed or invalid
config) are logged and the current in-memory config is kept, so a bad edit
never takes down a running process.

Note (Kubernetes): ConfigMaps mounted as volumes are updated by swapping a
symlink in the mount directory, so we watch the parent directory and match on
filename rather than watching the file inode directly.
"""

import logging
import threading
from pathlib import Path

from django.conf import settings
from watchfiles import Change, watch

from firetower import config_hooks
from firetower.config import ConfigFile
from firetower.settings import apply_config

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_started = False
_stop_event = threading.Event()


def reload_config() -> None:
    """Reload ``config.toml`` and apply it to the live settings, then run the hook."""
    path = settings.CONFIG_FILE_PATH
    old_config: ConfigFile | None = getattr(settings, "CONFIG", None)

    try:
        new_config = ConfigFile.from_file(path)
    except Exception:
        logger.exception("Failed to load config from %s; keeping current config", path)
        return

    try:
        apply_config(new_config)
    except Exception:
        logger.exception("Failed to apply reloaded config; settings may be partial")
        return

    logger.info("Reloaded configuration from %s", path)

    try:
        config_hooks.on_config_reload(old_config, new_config)
    except Exception:
        logger.exception("config reload hook raised")


def _watch_loop(config_path: Path) -> None:
    watch_dir = str(config_path.parent)
    filename = config_path.name

    def _only_config_file(_change: Change, changed_path: str) -> bool:
        return Path(changed_path).name == filename

    logger.info("Watching %s for changes", config_path)
    for changes in watch(
        watch_dir, watch_filter=_only_config_file, stop_event=_stop_event
    ):
        logger.info("Detected config change: %s", changes)
        reload_config()


def start_config_watcher() -> None:
    """
    Start the config watcher daemon thread for this process.

    Idempotent: only the first call per process starts a thread. No-op when the
    configured path does not exist on disk.
    """
    global _started  # noqa: PLW0603

    with _lock:
        if _started:
            return

        config_path = Path(settings.CONFIG_FILE_PATH)
        if not config_path.is_file():
            logger.warning("Config watcher not started: %s does not exist", config_path)
            return

        _stop_event.clear()
        thread = threading.Thread(
            target=_watch_loop,
            args=(config_path,),
            name="config-watcher",
            daemon=True,
        )
        thread.start()
        _started = True
        logger.info("Config watcher started for %s", config_path)


def stop_config_watcher() -> None:
    """Signal the watcher thread to stop. Mainly useful for tests."""
    global _started  # noqa: PLW0603
    _stop_event.set()
    with _lock:
        _started = False
