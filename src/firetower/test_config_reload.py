"""Tests for config.toml hot reloading (firetower.config_reload)."""

from dataclasses import replace
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
