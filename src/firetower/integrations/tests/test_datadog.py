from unittest.mock import MagicMock, patch

from datadog_api_client.exceptions import ApiException
from django.conf import settings

from firetower.integrations.services.datadog import (
    DATADOG_NOTEBOOK_BASE_URL,
    DatadogService,
)

MOCK_DATADOG_CONFIG = {
    "API_KEY": "test-api-key",
    "APP_KEY": "test-app-key",
}


class TestDatadogServiceInit:
    def test_init_with_config(self):
        with patch.object(settings, "DATADOG", MOCK_DATADOG_CONFIG):
            service = DatadogService()
            assert service.configured is True
            assert service.api_key == "test-api-key"
            assert service.app_key == "test-app-key"

    def test_init_without_config(self):
        with patch.object(settings, "DATADOG", None):
            service = DatadogService()
            assert service.configured is False
            assert service.api_key == ""
            assert service.app_key == ""

    def test_init_with_empty_api_key(self):
        config = {**MOCK_DATADOG_CONFIG, "API_KEY": ""}
        with patch.object(settings, "DATADOG", config):
            service = DatadogService()
            assert service.configured is False

    def test_init_with_empty_app_key(self):
        config = {**MOCK_DATADOG_CONFIG, "APP_KEY": ""}
        with patch.object(settings, "DATADOG", config):
            service = DatadogService()
            assert service.configured is False


class TestCreateNotebook:
    def _build_response(self, notebook_id: str = "abc-123") -> MagicMock:
        response = MagicMock()
        response.data.id = notebook_id
        return response

    def test_create_notebook_success(self):
        with patch.object(settings, "DATADOG", MOCK_DATADOG_CONFIG):
            service = DatadogService()

        mock_api = MagicMock()
        mock_api.create_notebook.return_value = self._build_response("nb-1")

        with patch(
            "firetower.integrations.services.datadog.NotebooksApi",
            return_value=mock_api,
        ):
            url = service.create_notebook("INC-100", "Database is on fire")

        assert url == f"{DATADOG_NOTEBOOK_BASE_URL}/nb-1"
        mock_api.create_notebook.assert_called_once()
        body = mock_api.create_notebook.call_args[1]["body"]
        assert body.data.attributes.name == "[INC-100] Database is on fire"
        assert body.data.attributes.cells == []
        assert str(body.data.attributes.time.live_span) == "1h"

    def test_create_notebook_truncates_long_title(self):
        with patch.object(settings, "DATADOG", MOCK_DATADOG_CONFIG):
            service = DatadogService()

        mock_api = MagicMock()
        mock_api.create_notebook.return_value = self._build_response("nb-2")

        long_title = "x" * 200
        with patch(
            "firetower.integrations.services.datadog.NotebooksApi",
            return_value=mock_api,
        ):
            service.create_notebook("INC-2000", long_title)

        body = mock_api.create_notebook.call_args[1]["body"]
        name = body.data.attributes.name
        assert len(name) == 80
        assert name.startswith("[INC-2000] ")
        assert name.endswith("...")

    def test_create_notebook_short_title_not_truncated(self):
        with patch.object(settings, "DATADOG", MOCK_DATADOG_CONFIG):
            service = DatadogService()

        mock_api = MagicMock()
        mock_api.create_notebook.return_value = self._build_response("nb-3")

        with patch(
            "firetower.integrations.services.datadog.NotebooksApi",
            return_value=mock_api,
        ):
            service.create_notebook("INC-1", "short")

        body = mock_api.create_notebook.call_args[1]["body"]
        assert body.data.attributes.name == "[INC-1] short"

    def test_create_notebook_returns_none_on_api_exception(self):
        with patch.object(settings, "DATADOG", MOCK_DATADOG_CONFIG):
            service = DatadogService()

        mock_api = MagicMock()
        mock_api.create_notebook.side_effect = ApiException(
            status=500, reason="Server Error"
        )

        with patch(
            "firetower.integrations.services.datadog.NotebooksApi",
            return_value=mock_api,
        ):
            url = service.create_notebook("INC-100", "title")

        assert url is None

    def test_create_notebook_returns_none_on_unexpected_exception(self):
        with patch.object(settings, "DATADOG", MOCK_DATADOG_CONFIG):
            service = DatadogService()

        mock_api = MagicMock()
        mock_api.create_notebook.side_effect = RuntimeError("network down")

        with patch(
            "firetower.integrations.services.datadog.NotebooksApi",
            return_value=mock_api,
        ):
            url = service.create_notebook("INC-100", "title")

        assert url is None

    def test_create_notebook_returns_none_when_unconfigured(self):
        with patch.object(settings, "DATADOG", None):
            service = DatadogService()

        with patch(
            "firetower.integrations.services.datadog.NotebooksApi"
        ) as mock_api_cls:
            url = service.create_notebook("INC-100", "title")

        assert url is None
        mock_api_cls.assert_not_called()

    def test_truncate_notebook_name_helper(self):
        with patch.object(settings, "DATADOG", MOCK_DATADOG_CONFIG):
            service = DatadogService()
        # exactly 80
        name = service._truncate_notebook_name("INC-9999", "x" * 100)
        assert len(name) == 80
        assert name.endswith("...")
        # short
        name = service._truncate_notebook_name("INC-1", "hi")
        assert name == "[INC-1] hi"
