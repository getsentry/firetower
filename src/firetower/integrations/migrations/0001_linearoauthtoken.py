from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="LinearOAuthToken",
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
                ("access_token", models.TextField()),
                ("expires_at", models.DateTimeField()),
                ("last_refreshed", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Linear OAuth Token",
            },
        ),
    ]
