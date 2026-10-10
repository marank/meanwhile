"""
Stores every calendar color role explicitly instead of deriving event and border colors in the client.

Existing calendars get event and border colors derived from their day color with the same formulas the
frontend palette generator (frontend/scripts/generate-calendar-palettes.ts) uses, so they look unchanged
and calendars on a preset still match it exactly.
"""

from django.db import migrations, models


def _channels(color):
    value = color.lstrip("#")
    return [int(value[i : i + 2], 16) for i in (0, 2, 4)]


def _js_round(value):
    # Math.round, which rounds .5 up (Python's round() rounds to even).
    return int(value + 0.5) if value >= 0 else -int(-value + 0.5)


def _hex(channels):
    return "#" + "".join(format(_js_round(c), "02x") for c in channels)


def _to_hsl(color):
    red, green, blue = (c / 255 for c in _channels(color))
    high, low = max(red, green, blue), min(red, green, blue)
    lightness = (high + low) / 2
    if high == low:
        return 0.0, 0.0, lightness
    delta = high - low
    saturation = delta / (2 - high - low) if lightness > 0.5 else delta / (high + low)
    if high == red:
        hue = (green - blue) / delta + (6 if green < blue else 0)
    elif high == green:
        hue = (blue - red) / delta + 2
    else:
        hue = (red - green) / delta + 4
    return hue * 60, saturation, lightness


def _from_hsl(hue, saturation, lightness):
    amount = saturation * min(lightness, 1 - lightness)

    def channel(n):
        k = (n + hue / 30) % 12
        return (lightness - amount * max(-1, min(k - 3, 9 - k, 1))) * 255

    return _hex([channel(0), channel(8), channel(4)])


def _shade(color, factor, boost=0.15, max_saturation=0.65):
    hue, saturation, lightness = _to_hsl(color)
    return _from_hsl(hue, min(max_saturation, saturation + boost), lightness * factor)


def _luminance(color):
    def linear(channel):
        value = channel / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(c) for c in _channels(color))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _darken_for_white_text(color):
    result = color
    step = 0
    while step < 20 and 1.05 / (_luminance(result) + 0.05) < 4.5:
        hue, saturation, lightness = _to_hsl(result)
        result = _from_hsl(hue, saturation, lightness * 0.93)
        step += 1
    return result


def _mix(color, target, amount):
    destination = _channels(target)
    return _hex([c + (destination[i] - c) * amount for i, c in enumerate(_channels(color))])


def derived_colors(base, dark):
    return {
        "event": _shade(base, 2.6, 0.2, 0.8) if dark else _darken_for_white_text(_shade(base, 0.6, 0.15, 0.6)),
        "border": _mix(base, "#ffffff" if dark else "#000000", 0.14 if dark else 0.16),
        "outer_border": _shade(base, 0.7 if dark else 0.36, 0.35 if dark else 0.2),
    }


def fill_derived_colors(apps, schema_editor):
    Calendar = apps.get_model("core", "Calendar")
    for calendar in Calendar.objects.all():
        for prefix, dark in (("", False), ("dark_", True)):
            for role, color in derived_colors(getattr(calendar, f"{prefix}base_color"), dark).items():
                setattr(calendar, f"{prefix}{role}_color", color)
        calendar.save(update_fields=[
            "event_color", "border_color", "outer_border_color",
            "dark_event_color", "dark_border_color", "dark_outer_border_color",
        ])


def char(default):
    return models.CharField(max_length=7, default=default)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_resource_archived_at"),
    ]

    operations = [
        migrations.RenameField("calendar", "color", "base_color"),
        migrations.RenameField("calendar", "dark_color", "dark_base_color"),
        # New defaults: the "blue" preset.
        migrations.AlterField("calendar", "base_color", char("#cbe0fe")),
        migrations.AlterField("calendar", "weekend_color", char("#bed1ed")),
        migrations.AlterField("calendar", "today_color", char("#80b3fe")),
        migrations.AlterField("calendar", "dark_base_color", char("#15253d")),
        migrations.AlterField("calendar", "dark_weekend_color", char("#22334c")),
        migrations.AlterField("calendar", "dark_today_color", char("#2b528b")),
        migrations.AddField("calendar", "event_color", char("#3372cc")),
        migrations.AddField("calendar", "border_color", char("#abbcd5")),
        migrations.AddField("calendar", "outer_border_color", char("#1d4988")),
        migrations.AddField("calendar", "dark_event_color", char("#215cb4")),
        migrations.AddField("calendar", "dark_border_color", char("#364458")),
        migrations.AddField("calendar", "dark_outer_border_color", char("#0a192f")),
        migrations.RunPython(fill_derived_colors, migrations.RunPython.noop),
    ]
