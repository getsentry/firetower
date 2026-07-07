from django.db import migrations

from firetower.incidents.tasks import SCHEDULES

SCHEDULE_NAME = "sweep_incident_recovery"


def create_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.get_or_create(
        name=SCHEDULE_NAME, defaults=SCHEDULES[SCHEDULE_NAME]
    )


def delete_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name=SCHEDULE_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0023_pendingincident"),
        ("django_q", "0018_task_success_index"),
    ]

    operations = [
        migrations.RunPython(create_schedule, delete_schedule),
    ]
