import logging
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from slack_bolt.adapter.socket_mode import SocketModeHandler

from firetower.slack_app.bolt import bolt_app

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Start the Slack bot in Socket Mode"

    def handle(self, *args: Any, **options: Any) -> None:
        app_token = settings.SLACK["APP_TOKEN"]
        handler = SocketModeHandler(app=bolt_app, app_token=app_token)
        logger.info("Starting Slack bot in Socket Mode")
        handler.start()
