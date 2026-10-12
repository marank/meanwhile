from django.db import migrations
from django.db.models import F


def staff_follows_superuser(apps, schema_editor):
    """is_staff is now set from is_superuser (User.save); staff without superuser couldn't do anything."""
    apps.get_model("core", "User").objects.update(is_staff=F("is_superuser"))


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0019_reminder_next_due_at"),
    ]

    operations = [
        migrations.RunPython(staff_follows_superuser, migrations.RunPython.noop),
    ]
