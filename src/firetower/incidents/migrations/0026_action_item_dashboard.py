from django.db import migrations, models

from firetower.incidents.tasks import SCHEDULES

SCHEDULE_NAME = "refresh_action_item_dashboard"


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
        ("incidents", "0025_alter_actionitem_created_at"),
        ("django_q", "0018_task_success_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="actionitem",
            name="linear_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="actionitem",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(create_schedule, delete_schedule),
    ]
