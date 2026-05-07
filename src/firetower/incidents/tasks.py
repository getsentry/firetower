from logging import info

from firetower.incidents.models import Incident

SCHEDULES = {
    "schedule_demo": {
        "func": "firetower.incidents.tasks.schedule_demo",
        "schedule_type": "I",  # Minutes
        "minutes": 5,
        "repeats": -1,  # repeat indefinitely
    },
}


def schedule_demo() -> None:
    incident = Incident.objects.order_by("-created_at").first()
    if incident:
        info(f"Most recent incident: INC-{incident.id}: {incident.title}")
    else:
        info("No incidents found.")
