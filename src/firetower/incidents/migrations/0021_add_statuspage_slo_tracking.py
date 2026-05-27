import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0020_add_slack_status_external_link_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="StatusPagePost",
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
                ("posted_at", models.DateTimeField()),
                (
                    "incident",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="statuspage_posts",
                        to="incidents.incident",
                    ),
                ),
            ],
            options={
                "ordering": ["posted_at"],
            },
        ),
        migrations.AddField(
            model_name="incident",
            name="statuspage_slo_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="incident",
            name="statuspage_slo_ended_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
