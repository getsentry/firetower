from django.db import migrations, models


def seed_counter(apps, schema_editor):
    """Seed the counter with MAX(id) + 1 or 2000 if no incidents exist."""
    IncidentCounter = apps.get_model("incidents", "IncidentCounter")
    Incident = apps.get_model("incidents", "Incident")

    max_id = Incident.objects.aggregate(max_id=models.Max("id"))["max_id"]
    next_id = (max_id + 1) if max_id is not None else 2000

    IncidentCounter.objects.create(next_id=next_id)


def reverse_seed_counter(apps, schema_editor):
    """Remove the counter row."""
    IncidentCounter = apps.get_model("incidents", "IncidentCounter")
    IncidentCounter.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0007_add_milestone_timestamps"),
    ]

    operations = [
        # Change id field from AutoField to PositiveIntegerField
        migrations.AlterField(
            model_name="incident",
            name="id",
            field=models.PositiveIntegerField(primary_key=True, serialize=False),
        ),
        # Create the counter table
        migrations.CreateModel(
            name="IncidentCounter",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("next_id", models.PositiveIntegerField(default=2000)),
            ],
            options={
                "db_table": "incidents_incident_counter",
            },
        ),
        # Seed the counter with the appropriate starting value
        migrations.RunPython(seed_counter, reverse_seed_counter),
    ]
