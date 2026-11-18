from django.db import migrations


def remove_demo_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name="schedule_demo").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0025_alter_actionitem_created_at"),
        ("django_q", "0018_task_success_index"),
    ]

    operations = [
        migrations.RunPython(remove_demo_schedule, migrations.RunPython.noop),
    ]
