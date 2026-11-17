from datetime import timedelta

from django.db import migrations, models
from django.utils import timezone

from firetower.incidents.tasks import SCHEDULES

SCHEDULE_NAME = "send_stale_incident_nudges"
RUN_HOUR_UTC = 14


def create_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    now = timezone.now()
    next_run = now.replace(hour=RUN_HOUR_UTC, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    Schedule.objects.get_or_create(
        name=SCHEDULE_NAME,
        defaults={**SCHEDULES[SCHEDULE_NAME], "next_run": next_run},
    )


def delete_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name=SCHEDULE_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0025_alter_actionitem_created_at"),
        ("django_q", "0018_task_success_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="incident",
            name="last_nudge_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(create_schedule, delete_schedule),
    ]
