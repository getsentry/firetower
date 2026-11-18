from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0027_stale_incident_nudges"),
        ("incidents", "0028_actionitem_linear_deadlines"),
    ]

    operations = []
