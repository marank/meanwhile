"""
Calendar color roles. Every role is stored for the light and the dark theme; text colors are not stored,
clients derive them for contrast.
"""

# Colors of the "blue" preset, which new calendars start with.
DEFAULT_COLORS = {
    "base_color": "#cbe0fe",
    "weekend_color": "#bed1ed",
    "today_color": "#80b3fe",
    "event_color": "#3372cc",
    "border_color": "#abbcd5",
    "outer_border_color": "#1d4988",
    "dark_base_color": "#15253d",
    "dark_weekend_color": "#22334c",
    "dark_today_color": "#2b528b",
    "dark_event_color": "#215cb4",
    "dark_border_color": "#364458",
    "dark_outer_border_color": "#0a192f",
}

# Colors of the "app" preset, which matches the app theme; the default for the calendar overview.
APP_COLORS = {
    "base_color": "#f6f6f7",
    "weekend_color": "#ededef",
    "today_color": "#dce6fa",
    "event_color": "#2261dd",
    "border_color": "#d4d4d8",
    "outer_border_color": "#a1a1aa",
    "dark_base_color": "#18181b",
    "dark_weekend_color": "#202024",
    "dark_today_color": "#1c2a47",
    "dark_event_color": "#2261dd",
    "dark_border_color": "#3f3f46",
    "dark_outer_border_color": "#52525b",
}

COLOR_FIELDS = tuple(DEFAULT_COLORS)
