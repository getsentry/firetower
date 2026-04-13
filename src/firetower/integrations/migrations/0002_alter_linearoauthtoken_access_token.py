import encrypted_fields.fields
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0001_linearoauthtoken"),
    ]

    operations = [
        migrations.AlterField(
            model_name="linearoauthtoken",
            name="access_token",
            field=encrypted_fields.fields.EncryptedTextField(),
        ),
    ]
