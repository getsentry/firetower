from django.db import migrations, models


def delete_jira_links(apps, schema_editor):
    ExternalLink = apps.get_model("incidents", "ExternalLink")
    ExternalLink.objects.filter(type="JIRA").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0013_add_tag_approved_field"),
    ]

    operations = [
        migrations.RunPython(delete_jira_links, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="externallink",
            name="type",
            field=models.CharField(
                choices=[
                    ("SLACK", "Slack"),
                    ("DATADOG", "Datadog"),
                    ("PAGERDUTY", "PagerDuty"),
                    ("STATUSPAGE", "Statuspage"),
                    ("NOTION", "Notion"),
                    ("LINEAR", "Linear"),
                ],
                max_length=20,
            ),
        ),
    ]
