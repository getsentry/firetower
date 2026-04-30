from django.db import migrations


def create_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.get_or_create(
        name="schedule_slo_nag",
        defaults={
            "func": "firetower.incidents.tasks.schedule_slo_nag",
            "schedule_type": "H",  # hourly
            "repeats": -1,  # repeat indefinitely
        },
    )


def delete_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name="schedule_slo_nag").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0014_add_total_downtime"),
        ("django_q", "0018_task_success_index"),
    ]

    operations = [
        migrations.RunPython(create_schedule, delete_schedule),
    ]
