from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0026_action_item_dashboard"),
    ]

    operations = [
        migrations.AddField(
            model_name="actionitem",
            name="linear_team_id",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="actionitem",
            name="linear_team_key",
            field=models.CharField(blank=True, default="", max_length=25),
        ),
        migrations.AddField(
            model_name="actionitem",
            name="linear_team_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
