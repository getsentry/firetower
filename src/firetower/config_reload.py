"""
Hot reload of ``config.toml`` by polling and hashing the file.

A daemon watcher thread is started once per process (see
``firetower.incidents.apps.IncidentsConfig.ready``). Because each Django
process — every web worker, the Slack bot, each q-cluster worker — holds its
own copy of ``django.conf.settings`` in memory, the watcher must run inside
each process; a standalone process could only mutate its own settings.

Detection is by periodic read + content hash rather than filesystem events
(inotify): Cloud Run runs under the gVisor sandbox, which does not deliver
inotify events, so an event-based watcher just times out. Hashing the file
contents (instead of comparing mtime) also transparently handles the symlink
swap that Kubernetes uses when updating a mounted ConfigMap.

When the hash changes the watcher rebuilds the config, re-applies every
config-derived setting via ``firetower.settings.apply_config``, then invokes
``firetower.config_hooks.on_config_reload``. Failures (a malformed or invalid
config) are logged and the current in-memory config is kept, so a bad edit
never takes down a running process.

Forking: ``fork()`` clones only the calling thread, so a forked child (e.g. a
django-q worker, or a preloaded gunicorn master's workers) does not inherit the
watcher thread, yet it does inherit the ``_started`` flag as ``True`` and never
re-runs ``AppConfig.ready``. Without intervention such children would watch
nothing and stay on stale settings. We therefore re-arm the watcher in the
child via ``os.register_at_fork``.
"""

import hashlib
import logging
import os
import threading
from pathlib import Path

from django.conf import settings

from firetower import config_hooks
from firetower.config import ConfigFile
from firetower.settings import apply_config

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_started = False
_stop_event = threading.Event()
_atfork_registered = False


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


def _hash_file(config_path: Path) -> str | None:
    """Return a hash of the file's contents, or ``None`` if it can't be read."""
    try:
        return hashlib.sha256(config_path.read_bytes()).hexdigest()
    except OSError:
        # Transient during a ConfigMap symlink swap, or the file was removed.
        logger.warning("Could not read %s while polling for changes", config_path)
        return None


def _poll_loop(config_path: Path, interval: float) -> None:
    logger.info("Polling %s for changes every %ss", config_path, interval)
    last_hash = _hash_file(config_path)

    # wait() returns True only when stop is signalled, so the loop ticks every
    # `interval` seconds until stopped, and shuts down promptly when it is.
    while not _stop_event.wait(interval):
        current_hash = _hash_file(config_path)
        if current_hash is None or current_hash == last_hash:
            continue

        logger.info("Detected config change in %s", config_path)
        reload_config()
        # Advance past this content even if the reload failed, so a persistently
        # invalid file isn't retried every tick; it will reload on the next edit.
        last_hash = current_hash


def start_config_watcher() -> None:
    """
    Start the config watcher daemon thread for this process.

    Idempotent: only the first call per process starts a thread. No-op when the
    configured path does not exist on disk. Also arms an ``os.register_at_fork``
    handler so forked children (which don't inherit the watcher thread) start
    their own.
    """
    global _started, _atfork_registered  # noqa: PLW0603

    with _lock:
        if _started:
            return

        config_path = Path(settings.CONFIG_FILE_PATH)
        if not config_path.is_file():
            logger.warning("Config watcher not started: %s does not exist", config_path)
            return

        _stop_event.clear()
        thread = threading.Thread(
            target=_poll_loop,
            args=(config_path, settings.CONFIG_WATCH_POLL_SECONDS),
            name="config-watcher",
            daemon=True,
        )
        thread.start()
        _started = True
        logger.info("Config watcher started for %s", config_path)

        if not _atfork_registered and hasattr(os, "register_at_fork"):
            # Inherited by children, so it only needs registering once.
            os.register_at_fork(after_in_child=_restart_after_fork)
            _atfork_registered = True


def _restart_after_fork() -> None:
    """
    Re-arm the watcher in a forked child.

    Runs in the child right after ``fork()``, while it is still single-threaded.
    The parent's watcher thread did not survive the fork, but ``_started`` was
    copied as ``True``. Replace the sync primitives (in case the parent held
    them at fork time) and start a fresh watcher for this process.
    """
    global _lock, _stop_event, _started  # noqa: PLW0603
    _lock = threading.Lock()
    _stop_event = threading.Event()
    _started = False
    start_config_watcher()


def stop_config_watcher() -> None:
    """Signal the watcher thread to stop. Mainly useful for tests."""
    global _started  # noqa: PLW0603
    _stop_event.set()
    with _lock:
        _started = False
