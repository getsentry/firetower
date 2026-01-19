from django.db import migrations


def fix_migration_history(apps, schema_editor):
    """Fix migration history if old-numbered migrations were already applied."""
    cursor = schema_editor.connection.cursor()

    # Check if old 0008 was applied under previous name
    cursor.execute(
        "SELECT 1 FROM django_migrations WHERE app = 'incidents' AND name = '0008_rename_affected_area_to_affected_service'"
    )
    if cursor.fetchone():
        # Rename old migration records to new names
        cursor.execute(
            "UPDATE django_migrations SET name = '0009_rename_affected_area_to_affected_service' "
            "WHERE app = 'incidents' AND name = '0008_rename_affected_area_to_affected_service'"
        )
        cursor.execute(
            "UPDATE django_migrations SET name = '0010_add_affected_region_tags' "
            "WHERE app = 'incidents' AND name = '0009_add_affected_region_tags'"
        )


def rename_field_if_needed(apps, schema_editor):
    """Only rename the M2M table if it hasn't been renamed already."""
    cursor = schema_editor.connection.cursor()

    # Check if the old table name still exists
    cursor.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'incidents_incident_affected_area_tags'"
    )
    if cursor.fetchone():
        # Old table exists, rename it
        cursor.execute(
            'ALTER TABLE "incidents_incident_affected_area_tags" RENAME TO "incidents_incident_affected_service_tags"'
        )


def reverse_rename_field(apps, schema_editor):
    """Reverse the rename."""
    cursor = schema_editor.connection.cursor()
    cursor.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'incidents_incident_affected_service_tags'"
    )
    if cursor.fetchone():
        cursor.execute(
            'ALTER TABLE "incidents_incident_affected_service_tags" RENAME TO "incidents_incident_affected_area_tags"'
        )


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0008_gapless_incident_ids"),
    ]

    operations = [
        # First, fix migration history if old migrations were already applied
        migrations.RunPython(fix_migration_history, migrations.RunPython.noop),
        # Rename the M2M field - use SeparateDatabaseAndState so Django knows about
        # the state change even if the DB operation is conditional
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameField(
                    model_name="incident",
                    old_name="affected_area_tags",
                    new_name="affected_service_tags",
                ),
            ],
            database_operations=[
                migrations.RunPython(rename_field_if_needed, reverse_rename_field),
            ],
        ),
        # Update Tag type values from AFFECTED_AREA to AFFECTED_SERVICE
        migrations.RunSQL(
            sql="UPDATE incidents_tag SET type = 'AFFECTED_SERVICE' WHERE type = 'AFFECTED_AREA'",
            reverse_sql="UPDATE incidents_tag SET type = 'AFFECTED_AREA' WHERE type = 'AFFECTED_SERVICE'",
        ),
    ]
