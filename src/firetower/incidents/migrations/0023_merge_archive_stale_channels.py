from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0019_schedule_archive_stale_channels"),
        ("incidents", "0022_actionitem_last_nag"),
    ]

    operations = []
