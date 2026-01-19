from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0008_gapless_incident_ids"),
    ]

    operations = [
        # Rename the M2M field from affected_area_tags to affected_service_tags
        migrations.RenameField(
            model_name="incident",
            old_name="affected_area_tags",
            new_name="affected_service_tags",
        ),
        # Update Tag type values from AFFECTED_AREA to AFFECTED_SERVICE
        migrations.RunSQL(
            sql="UPDATE incidents_tag SET type = 'AFFECTED_SERVICE' WHERE type = 'AFFECTED_AREA'",
            reverse_sql="UPDATE incidents_tag SET type = 'AFFECTED_AREA' WHERE type = 'AFFECTED_SERVICE'",
        ),
    ]
