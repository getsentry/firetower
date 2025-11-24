"""
Tests for health check endpoints and Datadog metrics integration.
"""

from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
class TestHealthChecks:
    """Test suite for health check endpoints."""

    def test_readiness_check_healthy(self):
        """Test readiness endpoint returns 200 when all checks pass."""
        client = Client()

        with patch("firetower.health.statsd.gauge") as mock_gauge:
            response = client.get(reverse("readiness"))

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "checks" in data
        assert data["checks"]["database"]["status"] == "pass"

        # Verify Datadog metric was sent
        mock_gauge.assert_called_once()
        call_args = mock_gauge.call_args
        assert call_args[0][0] == "firetower.ready"
        assert call_args[0][1] == 1

    def test_readiness_check_database_failure(self):
        """Test readiness endpoint returns 503 when database check fails."""
        client = Client()

        with (
            patch("firetower.health.check_database", return_value=(False, "DB error")),
            patch("firetower.health.statsd.gauge") as mock_gauge,
        ):
            response = client.get(reverse("readiness"))

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"]["status"] == "fail"

        # Verify Datadog metric was sent with value 0
        mock_gauge.assert_called_once()
        call_args = mock_gauge.call_args
        assert call_args[0][0] == "firetower.ready"
        assert call_args[0][1] == 0

    def test_readiness_check_datadog_failure_does_not_affect_response(self):
        """Test that Datadog metric failures don't affect health check response."""
        client = Client()

        with patch(
            "firetower.health.statsd.gauge", side_effect=Exception("Datadog error")
        ):
            response = client.get(reverse("readiness"))

        # Should still return successful response even if Datadog fails
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_liveness_check(self):
        """Test liveness endpoint returns 200 when service is running."""
        client = Client()

        response = client.get(reverse("liveness"))

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    def test_readiness_check_includes_environment_tag(self):
        """Test that readiness check includes environment tag in Datadog metric."""
        client = Client()

        with patch("firetower.health.statsd.gauge") as mock_gauge:
            client.get(reverse("readiness"))

        # Verify environment tag is included
        call_args = mock_gauge.call_args
        tags = call_args[1]["tags"]
        assert any(tag.startswith("environment:") for tag in tags)
        assert any(tag.startswith("status:") for tag in tags)
