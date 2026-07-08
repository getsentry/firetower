from django.db import migrations
from encrypted_fields.fields import EncryptedFieldMixin


def _encrypted_field_names(model) -> list[str]:
    """Return the names of any encrypted fields declared on ``model``."""
    return [
        field.name
        for field in model._meta.get_fields()
        if isinstance(field, EncryptedFieldMixin)
    ]


def reencrypt(apps, schema_editor):
    """Load and re-save every row of every model that has an encrypted field.

    Encrypted fields decrypt on read and encrypt on write, so a load/save
    cycle re-encrypts each value with the current primary key. Run this after
    rotating ``SALT_KEY`` (keeping the old key in the list so existing values
    can still be decrypted) to migrate all ciphertext onto the new key.
    """
    for model in apps.get_models():
        encrypted_fields = _encrypted_field_names(model)
        if not encrypted_fields:
            continue

        # ``update_fields`` limits the write to the encrypted columns, avoiding
        # side effects like bumping ``auto_now`` timestamps.
        for instance in model.objects.all().iterator():
            instance.save(update_fields=encrypted_fields)


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0002_alter_linearoauthtoken_access_token"),
    ]

    operations = [
        migrations.RunPython(reencrypt, migrations.RunPython.noop),
    ]
