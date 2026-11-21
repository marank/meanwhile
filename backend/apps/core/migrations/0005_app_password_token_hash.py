"""
App passwords are kept as the SHA-256 of their token instead of an Argon2 hash
(apps.core.services.app_passwords). Existing ones can't be converted (only their hash is known);
they are removed, and their users create new ones.
"""

from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def remove_app_passwords(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    apps.get_model("core", "AppPassword").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_email_unique_ignoring_case"),
    ]

    operations = [
        migrations.RunPython(remove_app_passwords, migrations.RunPython.noop),
        migrations.RemoveField(model_name="apppassword", name="password_hash"),
        migrations.AddField(
            model_name="apppassword",
            name="token_hash",
            field=models.CharField(default="", max_length=64, unique=True),
            preserve_default=False,
        ),
    ]
