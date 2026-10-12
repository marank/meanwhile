from django.db import migrations, models

LAYOUT_FIELDS = ("first_weekday", "show_weekends", "weekend_days", "show_week_numbers")


def follow_app_defaults(apps, schema_editor):
    """Values equal to the app's current defaults were most likely copied from them when the
    settings were created; they follow the defaults from now on. Others stay the user's choice."""
    app_settings = apps.get_model("core", "AppSettings").objects.filter(id=1).first()
    defaults = {
        field: getattr(app_settings, f"default_{field}") if app_settings else default
        for field, default in zip(LAYOUT_FIELDS, (0, True, [0, 6], False), strict=True)
    }
    OverviewSettings = apps.get_model("core", "OverviewSettings")
    for settings in OverviewSettings.objects.all():
        for field, default in defaults.items():
            if getattr(settings, field) == default:
                setattr(settings, field, None)
        settings.save(update_fields=LAYOUT_FIELDS)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_staff_follows_superuser"),
    ]

    operations = [
        migrations.AlterField(
            model_name="overviewsettings",
            name="first_weekday",
            field=models.IntegerField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name="overviewsettings",
            name="show_weekends",
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name="overviewsettings",
            name="weekend_days",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name="overviewsettings",
            name="show_week_numbers",
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
        migrations.RunPython(follow_app_defaults, migrations.RunPython.noop),
    ]
