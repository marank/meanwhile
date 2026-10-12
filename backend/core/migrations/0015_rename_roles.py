from django.db import migrations, models

RENAMES = {"viewer": "read", "contributor": "own", "editor": "full"}
FIELDS = [("Calendar", "public_role"), ("CalendarMember", "role"), ("CalendarGroup", "role")]
CHOICES = [("owner", "Owner"), ("full", "Full access"), ("own", "Own"), ("read", "Read only")]


def rename(mapping):
    def run(apps, schema_editor):
        for model, field in FIELDS:
            manager = apps.get_model("core", model).objects
            for old, new in mapping.items():
                manager.filter(**{field: old}).update(**{field: new})

    return run


class Migration(migrations.Migration):
    dependencies = [("core", "0014_email_and_imip")]

    operations = [
        migrations.RunPython(rename(RENAMES), rename({v: k for k, v in RENAMES.items()})),
        migrations.AlterField("calendar", "public_role", models.CharField(choices=CHOICES, default="read", max_length=20)),
        migrations.AlterField("calendarmember", "role", models.CharField(choices=CHOICES, default="read", max_length=20)),
        migrations.AlterField("calendargroup", "role", models.CharField(choices=CHOICES, default="read", max_length=20)),
    ]
