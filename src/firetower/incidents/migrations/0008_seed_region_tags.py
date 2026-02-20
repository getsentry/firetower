from django.db import migrations

REGION_TAGS = ["control", "de", "disney", "geico", "goldman-sachs", "ly", "s4s2", "us"]


def seed_region_tags(apps, schema_editor):
    Tag = apps.get_model("incidents", "Tag")
    for name in REGION_TAGS:
        Tag.objects.get_or_create(name=name, type="AFFECTED_AREA")


def remove_region_tags(apps, schema_editor):
    Tag = apps.get_model("incidents", "Tag")
    Tag.objects.filter(name__in=REGION_TAGS, type="AFFECTED_AREA").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0007_add_total_downtime"),
    ]

    operations = [
        migrations.RunPython(seed_region_tags, reverse_code=remove_region_tags),
    ]
