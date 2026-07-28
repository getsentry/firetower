"""Tests for config.toml hot reloading (firetower.config_reload)."""

import shutil
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase

from firetower import config_hooks, config_reload
from firetower.config import ConfigFile
from firetower.settings import apply_config


def _current_config() -> ConfigFile:
    return settings.CONFIG


class TestApplyConfig(TestCase):
    def setUp(self) -> None:
        self._original = _current_config()
        self.addCleanup(apply_config, self._original)

    def test_updates_derived_settings(self) -> None:
        new_config = replace(self._original, project_key="RELOADED")

        apply_config(new_config)

        self.assertEqual(settings.PROJECT_KEY, "RELOADED")
        self.assertIs(settings.CONFIG, new_config)

    def test_rebuilds_nested_dict_settings(self) -> None:
        new_slack = replace(self._original.slack, team_id="new-team")
        new_config = replace(self._original, slack=new_slack)

        apply_config(new_config)

        self.assertEqual(settings.SLACK["TEAM_ID"], "new-team")

    def test_invalid_config_raises_before_mutating(self) -> None:
        bad_auth = replace(self._original.auth, iap_enabled=True, iap_audience="")
        bad_config = replace(self._original, auth=bad_auth)

        with self.assertRaises(ValueError):
            apply_config(bad_config)

        self.assertIs(settings.CONFIG, self._original)


class TestReloadConfig(TestCase):
    def setUp(self) -> None:
        self._original = _current_config()
        self.addCleanup(apply_config, self._original)

    def test_applies_new_config_and_runs_hook(self) -> None:
        new_config = replace(self._original, project_key="FROM_DISK")

        with (
            patch.object(ConfigFile, "from_file", return_value=new_config),
            patch.object(config_hooks, "on_config_reload") as hook,
        ):
            config_reload.reload_config()

        self.assertEqual(settings.PROJECT_KEY, "FROM_DISK")
        hook.assert_called_once_with(self._original, new_config)

    def test_load_failure_keeps_current_config_and_skips_hook(self) -> None:
        with (
            patch.object(ConfigFile, "from_file", side_effect=OSError("boom")),
            patch.object(config_hooks, "on_config_reload") as hook,
        ):
            config_reload.reload_config()

        self.assertIs(settings.CONFIG, self._original)
        hook.assert_not_called()

    def test_hook_exception_is_swallowed(self) -> None:
        new_config = replace(self._original, project_key="HOOK_RAISED")

        with (
            patch.object(ConfigFile, "from_file", return_value=new_config),
            patch.object(
                config_hooks, "on_config_reload", side_effect=RuntimeError("nope")
            ),
        ):
            config_reload.reload_config()

        self.assertEqual(settings.PROJECT_KEY, "HOOK_RAISED")


class TestPollLoop(TestCase):
    def _make_config_file(self, contents: str) -> Path:
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, True)
        path = Path(tmpdir) / "config.toml"
        path.write_text(contents)
        return path

    def test_hash_file_returns_none_when_missing(self) -> None:
        missing = self._make_config_file("x = 1\n").parent / "missing.toml"
        self.assertIsNone(config_reload._hash_file(missing))

    def test_hash_changes_with_contents(self) -> None:
        path = self._make_config_file("a = 1\n")
        first = config_reload._hash_file(path)
        path.write_text("a = 2\n")
        self.assertNotEqual(first, config_reload._hash_file(path))

    def test_poll_reloads_only_when_contents_change(self) -> None:
        path = self._make_config_file("project_key = 'A'\n")

        # Change the file during the first sleep, then stop on the second.
        def wait(_interval: float) -> bool:
            if not writes:
                path.write_text("project_key = 'B'\n")
                writes.append(1)
                return False
            return True

        writes: list[int] = []
        with (
            patch.object(config_reload._stop_event, "wait", side_effect=wait),
            patch.object(config_reload, "reload_config") as reload_mock,
        ):
            config_reload._poll_loop(path, interval=0.01)

        reload_mock.assert_called_once()

    def test_poll_does_not_reload_when_unchanged(self) -> None:
        path = self._make_config_file("project_key = 'A'\n")

        with (
            patch.object(config_reload._stop_event, "wait", side_effect=[False, True]),
            patch.object(config_reload, "reload_config") as reload_mock,
        ):
            config_reload._poll_loop(path, interval=0.01)

        reload_mock.assert_not_called()

    def test_poll_does_not_retry_persistently_bad_file(self) -> None:
        path = self._make_config_file("project_key = 'A'\n")

        # Change the file once during the first sleep; it then stays changed
        # across several more ticks. reload_config must fire only once.
        def wait(_interval: float) -> bool:
            ticks.append(1)
            if len(ticks) == 1:
                path.write_text("project_key = 'B'\n")
                return False
            return len(ticks) >= 4

        ticks: list[int] = []
        with (
            patch.object(config_reload._stop_event, "wait", side_effect=wait),
            patch.object(config_reload, "reload_config") as reload_mock,
        ):
            config_reload._poll_loop(path, interval=0.01)

        reload_mock.assert_called_once()
