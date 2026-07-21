"""
Configuration file loader for Firetower.

Loads configuration values from a TOML file and validates that all required keys are present.
"""

import os
from dataclasses import field
from pathlib import Path
from typing import Any

from serde import deserialize, from_dict
from serde.toml import from_toml


class ConfigError(Exception):
    """Raised when a required secret is missing from both config and environment."""


# Secret handling (RELENG-918): every field marked `# secret` below is parse-
# optional (default "") so it can be supplied purely by its dedicated env var
# instead of the TOML file. Env values are applied by
# ConfigFile._apply_env_overrides (env wins when set and non-empty, else TOML),
# and ConfigFile._validate_required_secrets enforces that the required ones
# resolve to a non-empty value from either source. Secrets on an optional
# integration section are only required when that section is configured.


def _env_override(value: str, env_var: str) -> str:
    """
    Return the environment variable value if it is set and non-empty, else `value`.

    The non-empty guard is deliberate: a stray empty env var must not blank out a
    real secret coming from the TOML config. Unset or empty env vars fall back to
    the TOML value.
    """
    return v if (v := os.environ.get(env_var)) else value


@deserialize
class PostgresConfig:
    db: str
    host: str
    user: str
    password: str = ""  # secret: DJANGO_PG_PASS
    # Additional passwords tried (in order) only when `password` fails
    # authentication. Used to bridge the race window during a password
    # rotation, when the server and app may briefly disagree on the password.
    fallback_passwords: list[str] = field(default_factory=list)


@deserialize
class EscalationPolicy:
    id: str
    integration_key: str | None = None


@deserialize
class PagerDutyConfig:
    escalation_policies: dict[str, EscalationPolicy]
    api_token: str = ""  # secret: PAGERDUTY_API_TOKEN


@deserialize
class SlackConfig:
    team_id: str
    participant_sync_throttle_seconds: int
    bot_token: str = ""  # secret: SLACK_BOT_TOKEN
    app_token: str = ""  # secret: SLACK_APP_TOKEN
    incident_feed_channel_id: str = ""
    always_invited_ids: list[str] = field(default_factory=list)
    incident_guide_message: str = ""
    slash_command: str = "/inc"


@deserialize
class GenAIConfig:
    model: str = "gemini-2.5-flash"


@deserialize
class NotionConfig:
    database_id: str
    integration_token: str = ""  # secret: NOTION_INTEGRATION_TOKEN
    template_markdown: str = ""
    troubleshooting_database_id: str = ""
    troubleshooting_template_markdown: str = ""


@deserialize
class StatuspageConfig:
    page_id: str
    url: str
    api_key: str = ""  # secret: STATUSPAGE_API_KEY
    initial_reminder_delay_minutes: int | None = None
    followup_reminder_delay_minutes: int | None = None
    warning_buffer_minutes: int = 0


@deserialize
class LinearConfig:
    client_id: str = ""
    client_secret: str = ""  # secret: LINEAR_CLIENT_SECRET
    action_item_sync_throttle_seconds: int = 300
    team_id: str = ""
    project_id: str = ""
    sync_identifiers: bool = False
    adopt_on_create: bool = False
    api_key: str = ""
    alloc_timeout_seconds: int = 8
    alloc_max_retries: int = 1
    action_item_slo_days_high_priority: int = 14
    action_item_slo_days_medium_priority: int = 30
    action_item_nag_comment_high_priority: str = (
        "{% if days_past_due > 0 %}This action item is **{{ days_past_due }} "
        "day{% if days_past_due != 1 %}s{% endif %} past due**. {% endif %}"
        "The SLO for completing P0/P1 incident action items is {{ slo_days }} "
        "days from incident creation. Please prioritize this work or close "
        "out the issue if it is no longer relevant."
    )
    action_item_nag_comment_medium_priority: str = (
        "{% if days_past_due > 0 %}This action item is **{{ days_past_due }} "
        "day{% if days_past_due != 1 %}s{% endif %} past due**. {% endif %}"
        "The SLO for completing P2 incident action items is {{ slo_days }} "
        "days from incident creation. Please prioritize this work or close "
        "out the issue if it is no longer relevant."
    )
    parent_status_comment_completed: str = (
        "Firetower set this issue to **Completed**. "
        "Incident {{ incident.incident_number }} is {{ incident.status }} "
        "and {% if total_action_items == 0 %}there are no action items."
        "{% else %}all {{ total_action_items }} action "
        "item{% if total_action_items != 1 %}s{% endif %} are complete.{% endif %}"
    )
    parent_status_comment_started: str = (
        "Firetower set this issue to **Started**. "
        "Incident {{ incident.incident_number }} is {{ incident.status }}. "
        "{% if total_action_items == 0 %}There are no action items."
        "{% else %}{{ completed_action_items }} of {{ total_action_items }} action "
        "item{% if total_action_items != 1 %}s{% endif %} complete.{% endif %}"
    )


@deserialize
class AuthConfig:
    iap_enabled: bool
    iap_audience: str | None


@deserialize
class ConfigFile:
    """
    Load string configuration values from a TOML file.
    """

    postgres: PostgresConfig
    slack: SlackConfig
    linear: LinearConfig | None
    auth: AuthConfig
    pagerduty: PagerDutyConfig | None
    statuspage: StatuspageConfig | None

    project_key: str
    firetower_base_url: str
    sentry_dsn: str
    django_secret_key: str = ""  # secret: DJANGO_SECRET_KEY
    salt_key: str = ""  # secret: SALT_KEY (or salt_keys below)
    service_registry_url: str | None = None
    # When non-empty, `salt_keys` overrides `salt_key`. Used for key rotation:
    # values are encrypted with the first key and can be decrypted with any.
    salt_keys: list[str] = field(default_factory=list)
    notion: NotionConfig | None = None
    genai: GenAIConfig | None = None
    log_level: str = "INFO"
    hooks_enabled: bool = (
        False  # TODO: remove after hooks migration is complete and always enable
    )
    region_grouping: list[list[str]] = field(default_factory=list)

    @classmethod
    def from_file(cls, file_path: str | Path) -> "ConfigFile":
        """
        Load configuration from a TOML file.

        Args:
            file_path: Path to the TOML configuration file.

        Returns:
            ConfigFile instance with loaded configuration.
        """
        with open(file_path) as f:
            data: ConfigFile = from_toml(ConfigFile, f.read())
        data._apply_env_overrides()
        data._validate_required_secrets()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConfigFile":
        """
        Load configuration from a dictionary.

        Args:
            data: Dictionary containing configuration key-value pairs.

        Returns:
            ConfigFile instance with loaded configuration.
        """
        config = from_dict(ConfigFile, data)
        config._apply_env_overrides()
        config._validate_required_secrets()
        return config

    def _apply_env_overrides(self) -> None:
        """
        Override secret config values from dedicated environment variables.

        Applied as the single choke point after construction in both `from_file`
        and `from_dict` so every code path (and tests) shares one source of truth.
        Each override wins only when its env var is set AND non-empty; otherwise the
        TOML value is preserved (see `_env_override`). See RELENG-918.

        Note: SALT_KEY overrides only the singular salt_key; salt-key rotation uses
        the salt_keys list, which takes precedence in settings.py (rotate via the
        config file, not this env var). DJANGO_PG_PASS overrides only the primary
        postgres password; rotation uses postgres.fallback_passwords.
        """
        # (target, attribute, env var). target is None when its optional section
        # is absent, in which case the override is skipped.
        overrides: list[tuple[Any, str, str]] = [
            (self, "django_secret_key", "DJANGO_SECRET_KEY"),
            (self, "salt_key", "SALT_KEY"),
            (self.postgres, "password", "DJANGO_PG_PASS"),
            (self.slack, "bot_token", "SLACK_BOT_TOKEN"),
            (self.slack, "app_token", "SLACK_APP_TOKEN"),
            (self.linear, "client_secret", "LINEAR_CLIENT_SECRET"),
            (self.pagerduty, "api_token", "PAGERDUTY_API_TOKEN"),
            (self.statuspage, "api_key", "STATUSPAGE_API_KEY"),
            (self.notion, "integration_token", "NOTION_INTEGRATION_TOKEN"),
        ]
        for target, attr, env_var in overrides:
            if target is not None:
                setattr(target, attr, _env_override(getattr(target, attr), env_var))

        # Escalation keys can't use the flat table: the env var name is derived
        # per policy (PAGERDUTY_ESCALATION_KEY_<NAME>).
        if self.pagerduty is not None:
            for name, policy in self.pagerduty.escalation_policies.items():
                if override := os.environ.get(f"PAGERDUTY_ESCALATION_KEY_{name}"):
                    policy.integration_key = override

    def _validate_required_secrets(self) -> None:
        """
        Validate that required secrets are populated from either config or env.

        Run after `_apply_env_overrides` so a secret is considered present if it
        came from the TOML file OR its dedicated environment variable — the two are
        interchangeable sources. Secrets tied to an optional integration section are
        only required when that section is configured. Raises ConfigError listing
        every missing secret so a misconfigured deploy fails fast at boot rather
        than as an obscure downstream API/auth error. See RELENG-918.
        """
        # (label, is_satisfied): a secret is satisfied when it resolved to a
        # non-empty value from file or env, OR its optional section is absent (so
        # it is not required at all). Salt is satisfied by either the singular
        # salt_key or the salt_keys list (the plural is the rotation escape hatch
        # and takes precedence in settings.py). TODO(RELENG-918): revisit salt_keys.
        checks: list[tuple[str, bool]] = [
            (
                "django_secret_key (env: DJANGO_SECRET_KEY)",
                bool(self.django_secret_key),
            ),
            ("salt_key (env: SALT_KEY)", bool(self.salt_key or self.salt_keys)),
            (
                "postgres.password (env: DJANGO_PG_PASS)",
                self.postgres is None or bool(self.postgres.password),
            ),
            (
                "slack.bot_token (env: SLACK_BOT_TOKEN)",
                self.slack is None or bool(self.slack.bot_token),
            ),
            (
                "slack.app_token (env: SLACK_APP_TOKEN)",
                self.slack is None or bool(self.slack.app_token),
            ),
            (
                "pagerduty.api_token (env: PAGERDUTY_API_TOKEN)",
                self.pagerduty is None or bool(self.pagerduty.api_token),
            ),
            (
                "statuspage.api_key (env: STATUSPAGE_API_KEY)",
                self.statuspage is None or bool(self.statuspage.api_key),
            ),
            (
                "notion.integration_token (env: NOTION_INTEGRATION_TOKEN)",
                self.notion is None or bool(self.notion.integration_token),
            ),
        ]
        missing = [label for label, satisfied in checks if not satisfied]

        if missing:
            raise ConfigError(
                "Missing required secret(s), set via config file or environment: "
                + ", ".join(missing)
            )


class DummyConfigFile(ConfigFile):
    """
    A dummy configuration file for use when running collectstatic.
    """

    def __init__(self) -> None:
        self.postgres = PostgresConfig(
            db="firetower",
            host="localhost",
            user="postgres",
            password="dummy_dev_password",
            fallback_passwords=[],
        )
        self.slack = SlackConfig(
            bot_token="",
            team_id="",
            participant_sync_throttle_seconds=0,
            app_token="",
            incident_feed_channel_id="",
            always_invited_ids=[],
            incident_guide_message="",
        )
        self.auth = AuthConfig(
            iap_enabled=False,
            iap_audience="",
        )
        self.linear = None
        self.notion = None
        self.genai = None
        self.pagerduty = None
        self.statuspage = None
        self.project_key = ""
        self.firetower_base_url = ""
        self.django_secret_key = "dummy_value_DO_NOT_USE"
        self.salt_key = ""
        self.salt_keys = []
        self.sentry_dsn = ""
        self.service_registry_url = None
        self.region_grouping: list[list[str]] = []
        self.log_level = "INFO"
        self.hooks_enabled = False
