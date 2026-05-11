from django.db import migrations

from firetower.incidents.tasks import SCHEDULES


def create_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    schedule_name = "schedule_demo"
    Schedule.objects.get_or_create(
        name=schedule_name, defaults=SCHEDULES[schedule_name]
    )


def delete_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    schedule_name = "schedule_demo"
    Schedule.objects.filter(name=schedule_name).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0015_add_notion_troubleshooting_link_type"),
        ("django_q", "0018_task_success_index"),
    ]

    operations = [
        migrations.RunPython(create_schedule, delete_schedule),
    ]
