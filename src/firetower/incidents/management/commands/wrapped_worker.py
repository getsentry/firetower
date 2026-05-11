import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from django.core.management.base import BaseCommand
from django_q.conf import Conf
from django_q.humanhash import humanize
from django_q.status import Stat

logger = logging.getLogger(__name__)

_CLUSTER_NAME_RE = re.compile(r"Q Cluster (\S+) starting\.")

_state: dict[str, Any] = {}
_shutdown = threading.Event()


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        cluster_name = _state.get("cluster_name")

        if not cluster_name:
            self._respond(503, "cluster not yet started", None)
            return

        # TODO: this is awkward. Because the output is "humanized" we can't do a simple query.
        # TODO: is there maybe some way to un-humanize?
        target = next(
            (s for s in Stat.get_all() if humanize(s.cluster_id.hex) == cluster_name),
            None,
        )

        if target is None:
            self._respond(503, cluster_name, "not found or still starting")
        elif target.status in (Conf.IDLE, Conf.WORKING):
            self._respond(200, cluster_name, target.status)
        else:
            status = target.status
            self._respond(500, cluster_name, status)

    def _respond(self, code: int, cluster_name: str, status: Any) -> None:
        self.send_response(code)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(
            (
                "<html><head><title>Django-Q Health Check</title></head>"
                f"<body><p>Health check returned {code} response</p>"
                f"<p>Cluster {cluster_name} status: {status}</p></body></html>"
            ).encode()
        )

    def log_message(self, format: str, *args: Any) -> None:
        pass


def _start_health_server() -> HTTPServer:
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health check server listening on port %d", port)
    return server


def _handle_shutdown(signum: int, frame: Any) -> None:
    logger.info("Received signal %d, shutting down", signum)
    _shutdown.set()


class Command(BaseCommand):
    help = "Run a Q cluster subprocess wrapped with an HTTP health check server."

    def handle(self, *args: Any, **options: Any) -> None:
        _shutdown.clear()
        _state.clear()
        signal.signal(signal.SIGTERM, _handle_shutdown)
        signal.signal(signal.SIGINT, _handle_shutdown)

        server = _start_health_server()

        django_admin = shutil.which("django-admin")
        if django_admin is None or django_admin == "":
            django_admin = "/app/.venv/bin/django-admin"

        try:
            proc = subprocess.Popen(
                [django_admin, "qcluster", "--settings", "firetower.settings"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            def _pump_output() -> None:
                assert proc.stdout is not None
                for line in proc.stdout:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    if "cluster_name" not in _state:
                        match = _CLUSTER_NAME_RE.search(line)
                        if match:
                            _state["cluster_name"] = match.group(1)
                            logger.info("Detected cluster name: %s", match.group(1))

            pump_thread = threading.Thread(target=_pump_output, daemon=True)
            pump_thread.start()

            while not _shutdown.is_set():
                if proc.poll() is not None:
                    logger.warning(
                        "qcluster subprocess exited with code %s", proc.returncode
                    )
                    break
                _shutdown.wait(timeout=1)
        finally:
            server.shutdown()
            server.server_close()
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
