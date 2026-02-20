from django.db import migrations

IMPACT_TYPE_TAGS = ["Availability", "Latency", "Correctness", "Security"]


def seed_impact_type_tags(apps, schema_editor):
    Tag = apps.get_model("incidents", "Tag")
    for name in IMPACT_TYPE_TAGS:
        Tag.objects.get_or_create(name=name, type="IMPACT_TYPE")


def remove_impact_type_tags(apps, schema_editor):
    Tag = apps.get_model("incidents", "Tag")
    Tag.objects.filter(name__in=IMPACT_TYPE_TAGS, type="IMPACT_TYPE").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0015_seed_affected_region_tags"),
    ]

    operations = [
        migrations.RunPython(seed_impact_type_tags, reverse_code=remove_impact_type_tags),
    ]
