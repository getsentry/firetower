import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from slack_bolt.adapter.socket_mode import SocketModeHandler

from firetower.slack_app.bolt import get_bolt_app

logger = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self, *args: Any) -> None:
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        pass


def _start_health_server() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health check server listening on port %d", port)


class Command(BaseCommand):
    help = "Start the Slack bot in Socket Mode"

    def handle(self, *args: Any, **options: Any) -> None:
        _start_health_server()
        app_token = settings.SLACK["APP_TOKEN"]
        handler = SocketModeHandler(app=get_bolt_app(), app_token=app_token)
        logger.info("Starting Slack bot in Socket Mode")
        handler.start()
