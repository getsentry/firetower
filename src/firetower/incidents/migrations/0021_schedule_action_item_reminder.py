from django.db import migrations

from firetower.incidents.tasks import SCHEDULES

SCHEDULE_NAME = "send_action_item_reminder"


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
        ("incidents", "0020_add_slack_status_external_link_type"),
        ("django_q", "0018_task_success_index"),
    ]

    operations = [
        migrations.RunPython(create_schedule, delete_schedule),
    ]
