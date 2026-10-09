import pytest

from firetower.mcp_server.config import ConfigError, MCPConfig


@pytest.fixture
def required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("MCP_GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("MCP_BASE_URL", "https://mcp.example.com")
    monkeypatch.setenv("FIRETOWER_SERVICE_ACCOUNT", "test@example.com")
    monkeypatch.setenv("MCP_JWT_SIGNING_KEY", "test-signing-key")
    monkeypatch.setenv(
        "MCP_ALLOWED_REDIRECT_URIS", "https://client.example.com/callback"
    )


def test_jwt_signing_key_is_required(
    monkeypatch: pytest.MonkeyPatch, required_env: None
) -> None:
    monkeypatch.delenv("MCP_JWT_SIGNING_KEY")

    with pytest.raises(ConfigError, match="MCP_JWT_SIGNING_KEY"):
        MCPConfig.from_env()


@pytest.mark.parametrize("value", ["", " \t "])
def test_blank_firetower_url_is_unset(
    monkeypatch: pytest.MonkeyPatch, required_env: None, value: str
) -> None:
    monkeypatch.setenv("FIRETOWER_URL", value)

    assert MCPConfig.from_env().firetower_url is None


def test_custom_firetower_url_is_trimmed(
    monkeypatch: pytest.MonkeyPatch, required_env: None
) -> None:
    monkeypatch.setenv("FIRETOWER_URL", "  https://firetower.example.com  ")

    assert MCPConfig.from_env().firetower_url == "https://firetower.example.com"


@pytest.mark.parametrize("name", ["MCP_BOT_ISSUER", "MCP_BOT_JWKS_URL"])
def test_bot_auth_requires_issuer_and_jwks_together(
    monkeypatch: pytest.MonkeyPatch, required_env: None, name: str
) -> None:
    monkeypatch.setenv(name, "https://junior.example")

    with pytest.raises(ConfigError, match="must be set together"):
        MCPConfig.from_env()


def test_bot_auth_is_configured_from_env(
    monkeypatch: pytest.MonkeyPatch, required_env: None
) -> None:
    monkeypatch.setenv("MCP_BOT_ISSUER", "https://junior.example")
    monkeypatch.setenv("MCP_BOT_JWKS_URL", "https://junior.example/jwks.json")

    config = MCPConfig.from_env()

    assert config.bot_issuer == "https://junior.example"
    assert config.bot_jwks_url == "https://junior.example/jwks.json"


@pytest.mark.parametrize("name", ["MCP_BOT_ISSUER", "MCP_BOT_JWKS_URL"])
@pytest.mark.parametrize(
    "value",
    [
        "http://junior.example",
        "junior.example/jwks.json",
        "/.well-known/jwks.json",
        "https://",
        "https:///jwks.json",
        "https://[::1",
    ],
)
def test_bot_auth_urls_must_be_absolute_https(
    monkeypatch: pytest.MonkeyPatch, required_env: None, name: str, value: str
) -> None:
    monkeypatch.setenv("MCP_BOT_ISSUER", "https://junior.example")
    monkeypatch.setenv("MCP_BOT_JWKS_URL", "https://junior.example/jwks.json")
    monkeypatch.setenv(name, value)

    with pytest.raises(ConfigError, match=f"{name} must be an absolute https://"):
        MCPConfig.from_env()
