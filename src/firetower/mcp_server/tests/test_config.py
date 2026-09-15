import pytest

from firetower.mcp_server.config import MCPConfig


@pytest.fixture
def required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("MCP_GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("MCP_BASE_URL", "https://mcp.example.com")
    monkeypatch.setenv("FIRETOWER_SERVICE_ACCOUNT", "test@example.com")
    monkeypatch.setenv(
        "MCP_ALLOWED_REDIRECT_URIS", "https://client.example.com/callback"
    )


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
