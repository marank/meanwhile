from django.db import migrations, models

LAYOUT_FIELDS = ("first_weekday", "show_weekends", "weekend_days", "show_week_numbers")


def follow_app_defaults(apps, schema_editor):
    """Values equal to the app's current defaults were most likely copied from them when the
    calendar was created; they follow the defaults from now on. Others stay as chosen."""
    app_settings = apps.get_model("core", "AppSettings").objects.filter(id=1).first()
    for field, default in zip(LAYOUT_FIELDS, (0, True, [0, 6], False), strict=True):
        value = getattr(app_settings, f"default_{field}") if app_settings else default
        calendars = apps.get_model("core", "Calendar").objects.all()
        if field == "weekend_days":
            # JSON is compared as a whole; filtering on it differs between databases.
            ids = [c.id for c in calendars.only("id", field) if c.weekend_days == value]
            calendars.filter(id__in=ids).update(weekend_days=None)
        else:
            calendars.filter(**{field: value}).update(**{field: None})


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0021_overview_layout_follows_app_defaults"),
    ]

    operations = [
        migrations.AlterField(
            model_name="calendar",
            name="first_weekday",
            field=models.IntegerField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name="calendar",
            name="show_weekends",
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name="calendar",
            name="weekend_days",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name="calendar",
            name="show_week_numbers",
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
        migrations.RunPython(follow_app_defaults, migrations.RunPython.noop),
    ]
