from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0027_actionitem_linear_team"),
    ]

    operations = [
        migrations.AddField(
            model_name="actionitem",
            name="linear_due_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="actionitem",
            name="linear_sla_breaches_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
