"""Tests for config loading, env-var overrides, and required-secret validation."""

import pytest

from firetower.config import ConfigError, ConfigFile

# Every env var that _apply_env_overrides consults. Cleared before each test so
# ambient secrets in the CI/dev environment can't override file values or
# satisfy a deliberately-missing secret (which would flake these tests).
_SECRET_ENV_VARS = (
    "DJANGO_SECRET_KEY",
    "SALT_KEY",
    "DJANGO_PG_PASS",
    "SLACK_BOT_TOKEN",
    "SLACK_APP_TOKEN",
    "LINEAR_CLIENT_SECRET",
    "PAGERDUTY_API_TOKEN",
    "PAGERDUTY_ESCALATION_KEY_IMOC",
    "STATUSPAGE_API_KEY",
    "NOTION_INTEGRATION_TOKEN",
)


@pytest.fixture(autouse=True)
def _clear_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate every test from ambient secret env vars.

    Tests that need an override set it explicitly with monkeypatch.setenv after
    this fixture has cleared the baseline.
    """
    for var in _SECRET_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _minimal_config() -> dict:
    """A minimal config dict with every required secret present in-file."""
    return {
        "project_key": "INC",
        "firetower_base_url": "http://localhost",
        "sentry_dsn": "",
        "django_secret_key": "file-django-key",
        "salt_key": "file-salt",
        "postgres": {
            "db": "firetower",
            "host": "localhost",
            "user": "postgres",
            "password": "file-pg-pass",
        },
        "slack": {
            "team_id": "T1",
            "participant_sync_throttle_seconds": 300,
            "bot_token": "file-bot",
            "app_token": "file-app",
        },
        "auth": {"iap_enabled": False, "iap_audience": ""},
    }


def test_secrets_from_file_load_cleanly() -> None:
    config = ConfigFile.from_dict(_minimal_config())
    assert config.django_secret_key == "file-django-key"
    assert config.slack.bot_token == "file-bot"
    assert config.postgres.password == "file-pg-pass"


def test_required_secret_supplied_purely_by_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A required secret absent from TOML is satisfied by its env var."""
    monkeypatch.setenv("DJANGO_SECRET_KEY", "env-django-key")
    data = _minimal_config()
    del data["django_secret_key"]  # not in file; must come from env

    config = ConfigFile.from_dict(data)

    assert config.django_secret_key == "env-django-key"


def test_env_wins_over_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "env-bot")
    config = ConfigFile.from_dict(_minimal_config())
    assert config.slack.bot_token == "env-bot"


def test_empty_env_falls_back_to_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty env var must not blank out a real file value."""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "")
    config = ConfigFile.from_dict(_minimal_config())
    assert config.slack.bot_token == "file-bot"


def test_missing_required_secret_from_both_raises() -> None:
    data = _minimal_config()
    del data["django_secret_key"]  # absent from file, no env var set

    with pytest.raises(ConfigError, match="DJANGO_SECRET_KEY"):
        ConfigFile.from_dict(data)


def test_salt_satisfied_by_salt_keys_when_salt_key_empty() -> None:
    data = _minimal_config()
    data["salt_key"] = ""
    data["salt_keys"] = ["rotated-salt"]

    config = ConfigFile.from_dict(data)

    assert config.salt_key == ""
    assert config.salt_keys == ["rotated-salt"]


def test_missing_salt_entirely_raises() -> None:
    data = _minimal_config()
    data["salt_key"] = ""

    with pytest.raises(ConfigError, match="SALT_KEY"):
        ConfigFile.from_dict(data)


def test_optional_section_absent_is_not_required() -> None:
    """No [pagerduty]/[statuspage]/[notion] section => their tokens aren't required."""
    config = ConfigFile.from_dict(_minimal_config())
    assert config.pagerduty is None
    assert config.statuspage is None
    assert config.notion is None


def test_present_section_requires_its_token() -> None:
    data = _minimal_config()
    data["statuspage"] = {"page_id": "p1", "url": "https://s.io/", "api_key": ""}

    with pytest.raises(ConfigError, match="STATUSPAGE_API_KEY"):
        ConfigFile.from_dict(data)


def test_present_section_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STATUSPAGE_API_KEY", "env-sp-key")
    data = _minimal_config()
    data["statuspage"] = {"page_id": "p1", "url": "https://s.io/", "api_key": ""}

    config = ConfigFile.from_dict(data)

    assert config.statuspage is not None
    assert config.statuspage.api_key == "env-sp-key"


def test_pagerduty_escalation_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAGERDUTY_ESCALATION_KEY_IMOC", "env-imoc-key")
    data = _minimal_config()
    data["pagerduty"] = {
        "api_token": "file-pd-token",
        "escalation_policies": {"IMOC": {"id": "PABC123"}},
    }

    config = ConfigFile.from_dict(data)

    assert config.pagerduty is not None
    assert (
        config.pagerduty.escalation_policies["IMOC"].integration_key == "env-imoc-key"
    )


def test_multiple_missing_secrets_all_reported() -> None:
    data = _minimal_config()
    del data["django_secret_key"]
    data["postgres"]["password"] = ""

    with pytest.raises(ConfigError) as exc_info:
        ConfigFile.from_dict(data)

    message = str(exc_info.value)
    assert "DJANGO_SECRET_KEY" in message
    assert "DJANGO_PG_PASS" in message
