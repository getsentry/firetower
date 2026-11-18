from django_q.tasks import Schedule

from firetower.incidents.tasks.action_items import send_action_item_reminder
from firetower.incidents.tasks.decorators import datadog_log
from firetower.incidents.tasks.stale_incidents import send_stale_incident_nudges
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
    "send_action_item_reminder",
    "send_stale_incident_nudges",
    "send_statuspage_followup_reminder",
    "send_statuspage_reminder",
]

SCHEDULES = {
    "send_action_item_reminder": {
        "func": "firetower.incidents.tasks.send_action_item_reminder",
        "schedule_type": Schedule.MINUTES,
        "minutes": 30,
        "repeats": -1,
    },
    "send_stale_incident_nudges": {
        "func": "firetower.incidents.tasks.send_stale_incident_nudges",
        "schedule_type": Schedule.HOURLY,
        "repeats": -1,
    },
}
