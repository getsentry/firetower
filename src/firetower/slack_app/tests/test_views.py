import hashlib
import hmac
import time
from unittest.mock import patch

import pytest
from django.conf import settings
from django.http import HttpResponse
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestSlackEventsEndpoint:
    def setup_method(self):
        self.client = APIClient()
        self.url = "/slack/events"
        self.signing_secret = settings.SLACK["SIGNING_SECRET"]

    def _sign_request(self, body: str, timestamp: str | None = None):
        ts = timestamp or str(int(time.time()))
        sig_basestring = f"v0:{ts}:{body}"
        signature = (
            "v0="
            + hmac.new(
                self.signing_secret.encode("utf-8"),
                sig_basestring.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        )
        return ts, signature

    def test_missing_auth_headers_returns_403(self):
        response = self.client.post(
            self.url,
            data="command=/inc&text=help",
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 403

    def test_invalid_signature_returns_403(self):
        ts = str(int(time.time()))
        response = self.client.post(
            self.url,
            data="command=/inc&text=help",
            content_type="application/x-www-form-urlencoded",
            HTTP_X_SLACK_REQUEST_TIMESTAMP=ts,
            HTTP_X_SLACK_SIGNATURE="v0=invalidsignature",
        )
        assert response.status_code == 403

    def test_expired_timestamp_returns_403(self):
        old_ts = str(int(time.time()) - 300)
        body = "command=/inc&text=help"
        _, signature = self._sign_request(body, old_ts)
        response = self.client.post(
            self.url,
            data=body,
            content_type="application/x-www-form-urlencoded",
            HTTP_X_SLACK_REQUEST_TIMESTAMP=old_ts,
            HTTP_X_SLACK_SIGNATURE=signature,
        )
        assert response.status_code == 403

    @patch("firetower.slack_app.views.handler")
    def test_valid_signature_returns_200(self, mock_handler):
        mock_handler.handle.return_value = HttpResponse(status=200)

        body = "command=/inc&text=help"
        ts, signature = self._sign_request(body)
        response = self.client.post(
            self.url,
            data=body,
            content_type="application/x-www-form-urlencoded",
            HTTP_X_SLACK_REQUEST_TIMESTAMP=ts,
            HTTP_X_SLACK_SIGNATURE=signature,
        )
        assert response.status_code == 200
        mock_handler.handle.assert_called_once()

    @patch("firetower.slack_app.views.handler")
    def test_csrf_not_enforced(self, mock_handler):
        mock_handler.handle.return_value = HttpResponse(status=200)

        body = "command=/inc&text=help"
        ts, signature = self._sign_request(body)
        response = self.client.post(
            self.url,
            data=body,
            content_type="application/x-www-form-urlencoded",
            HTTP_X_SLACK_REQUEST_TIMESTAMP=ts,
            HTTP_X_SLACK_SIGNATURE=signature,
        )
        assert response.status_code == 200
