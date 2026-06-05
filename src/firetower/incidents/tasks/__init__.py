import logging

from django_q.tasks import Schedule

from firetower.incidents.models import Incident
from firetower.incidents.tasks.action_items import send_action_item_reminder
from firetower.incidents.tasks.decorators import datadog_log
from firetower.incidents.tasks.statuspage import (
    STATUSPAGE_FOLLOWUP_REMINDER_MESSAGE,
    STATUSPAGE_REMINDER_MESSAGE,
    send_statuspage_followup_reminder,
    send_statuspage_reminder,
)

__all__ = [
    "SCHEDULES",
    "STATUSPAGE_FOLLOWUP_REMINDER_MESSAGE",
    "STATUSPAGE_REMINDER_MESSAGE",
    "datadog_log",
    "schedule_demo",
    "send_action_item_reminder",
    "send_statuspage_followup_reminder",
    "send_statuspage_reminder",
]

logger = logging.getLogger(__name__)

SCHEDULES = {
    "schedule_demo": {
        "func": "firetower.incidents.tasks.schedule_demo",
        "schedule_type": Schedule.MINUTES,  # Minutes
        "minutes": 5,
        "repeats": -1,  # repeat indefinitely
    },
    "send_action_item_reminder": {
        "func": "firetower.incidents.tasks.send_action_item_reminder",
        "schedule_type": Schedule.MINUTES,
        "minutes": 30,
        "repeats": -1,
    },
}


@datadog_log
def schedule_demo() -> None:
    incident = Incident.objects.order_by("-created_at").first()
    if incident:
        title = "Private Incident" if incident.is_private else incident.title
        logger.info(f"Most recent incident: INC-{incident.id}: {title}")
    else:
        logger.info("No incidents found.")
