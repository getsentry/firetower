from unittest.mock import Mock, call, patch

import pytest
from django.test import RequestFactory

from firetower.incidents.metrics.middleware import MetricsMiddleware


class TestMetricsMiddleware:
    @pytest.fixture
    def factory(self):
        return RequestFactory()

    @pytest.fixture
    def get_response(self):
        return Mock()

    @patch("datadog.statsd.increment")
    def test_path_name(self, mock_increment, factory, get_response):
        get_response.return_value.status_code = 200
        request = factory.get("/api/users/me")

        middleware = MetricsMiddleware(get_response)
        middleware(request)

        mock_increment.assert_has_calls(
            [
                call("django.request", tags=["path:/api/users/me"]),
                call("django.response", tags=["path:/api/users/me", "code:200"]),
            ]
        )
        assert mock_increment.call_count == 2

    @patch("datadog.statsd.increment")
    def test_path_name_numbers(self, mock_increment, factory, get_response):
        get_response.return_value.status_code = 500
        request = factory.get("/api/ui/incidents/INC-2000")

        middleware = MetricsMiddleware(get_response)
        middleware(request)

        mock_increment.assert_has_calls(
            [
                call("django.request", tags=["path:/api/ui/incidents/inc-:NUM:"]),
                call(
                    "django.response",
                    tags=["path:/api/ui/incidents/inc-:NUM:", "code:500"],
                ),
            ]
        )
        assert mock_increment.call_count == 2

    @patch("datadog.statsd.increment")
    def test_path_name_weird_characters(self, mock_increment, factory, get_response):
        get_response.return_value.status_code = 200
        request = factory.get("/WEIRD~/stuff!/%here")

        middleware = MetricsMiddleware(get_response)
        middleware(request)

        mock_increment.assert_has_calls(
            [
                call("django.request", tags=["path:/weird_/stuff_/_here"]),
                call(
                    "django.response",
                    tags=["path:/weird_/stuff_/_here", "code:200"],
                ),
            ]
        )
        assert mock_increment.call_count == 2
