from logging import info

SCHEDULES = {
    "schedule_demo": {
        "func": "firetower.incidents.tasks.schedule_demo",
        "schedule_type": "I",  # Minutes
        "minutes": 5,
        "repeats": -1,  # repeat indefinitely
    },
}


def schedule_demo() -> None:
    info("hello world")
