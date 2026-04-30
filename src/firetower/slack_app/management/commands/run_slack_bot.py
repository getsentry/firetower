import logging
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from slack_bolt.adapter.socket_mode import SocketModeHandler

from firetower.slack_app.bolt import get_bolt_app

logger = logging.getLogger(__name__)

_shutdown = threading.Event()


def _on_close(close_status_code: int, close_msg: str | None) -> None:
    logger.warning(
        "Slack WebSocket connection closed (code=%s): %s", close_status_code, close_msg
    )


def _on_error(error: Exception) -> None:
    logger.error("Slack WebSocket error: %s", error)


def _handle_shutdown(signum: int, frame: Any) -> None:
    logger.info("Received signal %d, shutting down", signum)
    _shutdown.set()


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
        signal.signal(signal.SIGTERM, _handle_shutdown)
        signal.signal(signal.SIGINT, _handle_shutdown)
        app_token = settings.SLACK["APP_TOKEN"]
        while not _shutdown.is_set():
            try:
                handler = SocketModeHandler(app=get_bolt_app(), app_token=app_token)
                handler.client.on_close_listeners.append(_on_close)
                handler.client.on_error_listeners.append(_on_error)
                logger.info("Starting Slack bot in Socket Mode")
                handler.start()
            except Exception as e:
                if _shutdown.is_set():
                    break
                logger.error("Slack bot crashed: %s, restarting in 5s", e)
                time.sleep(5)
