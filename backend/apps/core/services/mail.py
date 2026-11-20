"""
Sending emails: notifications and invitations.

Messages are built during the request (from the data as it is then) and go out as jobs of the task
queue (apps.core.tasks), which are saved along with the request's changes: a slow or unreachable mail
server neither holds up nor fails the request, and the worker tries again until it takes them.
"""

import base64
import binascii
import email.message
import email.policy
import logging
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from email.policy import Policy
from email.utils import formataddr
from html import escape
from pathlib import Path
from typing import Any, Literal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction

from apps.core import jobs
from apps.core.models.events import Event
from apps.core.models.users import User, get_or_create_app_settings
from apps.core.services.mail_texts import text
from apps.core.services.recurrence import as_utc, zone
from apps.core.services.unsubscribe import make_token

logger = logging.getLogger(__name__)


def app_name() -> str:
    return get_or_create_app_settings().app_name or "Meanwhile"


def one_line(value: str) -> str:
    """Text for a header: event titles and names from CalDAV clients may span lines, which headers
    can't (Django raises BadHeaderError)."""
    return " ".join(value.split())


def sender(name: str | None = None, app: str | None = None) -> str:
    """The From address: the app's address, under the name of whoever acts, if anyone."""
    app = one_line(app or app_name())
    name = one_line(name) if name else None
    return formataddr((f"{name} ({app})" if name else app, settings.DEFAULT_FROM_EMAIL))


def language_of(user: User | None, fallback: str = "en") -> str:
    language = (user.language if user else "") or fallback
    return language if language in ("en", "de") else "en"


def app_link(path: str) -> str:
    """An absolute link into the app."""
    return f"{settings.APP_URL}{path}"


# Logo ----------------------------------------------------------------------------------------

_DEFAULT_LOGO = Path(__file__).resolve().parent.parent / "assets" / "mail-logo.png"
# Every email carries the logo, so a big upload isn't sent along (the app's name is shown alone).
_MAX_LOGO_BYTES = 200_000
_UPLOADED_IMAGE = re.compile(r"data:image/(png|jpeg|gif);base64,(.+)", re.DOTALL)
LOGO_CID = "logo@meanwhile"


@dataclass
class InlineImage:
    data: bytes
    subtype: str


def logo() -> InlineImage | str | None:
    """The logo at the top of emails: the uploaded one, else ours. Images come along with the email, as
    mail programs show those at once but load linked ones only when asked; PNG, JPEG and GIF only (Gmail
    and Outlook show no SVG). A logo given as an address stays a link; None for one that can't be sent."""
    uploaded = get_or_create_app_settings().logo_url
    if not uploaded:
        return InlineImage(_DEFAULT_LOGO.read_bytes(), "png")
    if uploaded.startswith("/"):
        return app_link(uploaded)
    if uploaded.startswith(("https://", "http://")):
        return uploaded
    match = _UPLOADED_IMAGE.fullmatch(uploaded)
    if not match:
        return None
    try:
        data = base64.b64decode(match[2], validate=True)
    except binascii.Error:
        return None
    return InlineImage(data, match[1]) if len(data) <= _MAX_LOGO_BYTES else None


# Times ----------------------------------------------------------------------------------------

_WEEKDAYS = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "de": ["Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."],
}
_MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "de": ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sep.", "Okt.", "Nov.", "Dez."],
}
_WEEKDAYS_LONG = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "de": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
}
_MONTHS_LONG = {
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
    "de": [
        "Januar",
        "Februar",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember",
    ],
}


@dataclass
class Reader:
    """How a recipient reads times: language, zone and clock."""

    language: str = "en"
    timezone: str = "UTC"
    twelve_hour: bool = False

    @classmethod
    def of(cls, user: User | None, language: str, timezone: str) -> Reader:
        clock = user.time_format if user else "auto"
        twelve = clock == "12h" or (clock == "auto" and language == "en")
        return cls(language, (user.timezone if user else "") or timezone or "UTC", twelve)


def _date(day: date, reader: Reader) -> str:
    weekday = _WEEKDAYS[reader.language][day.weekday()]
    month = _MONTHS[reader.language][day.month - 1]
    if reader.language == "de":
        return f"{weekday}, {day.day}. {month} {day.year}"
    return f"{weekday}, {month} {day.day}, {day.year}"


def _long_date(day: date, reader: Reader) -> str:
    weekday = _WEEKDAYS_LONG[reader.language][day.weekday()]
    month = _MONTHS_LONG[reader.language][day.month - 1]
    if reader.language == "de":
        return f"{weekday}, {day.day}. {month} {day.year}"
    return f"{weekday}, {month} {day.day}, {day.year}"


def _time(moment: datetime, reader: Reader) -> str:
    if reader.twelve_hour:
        hour = moment.hour % 12 or 12
        return f"{hour}:{moment.minute:02d} {'AM' if moment.hour < 12 else 'PM'}"
    return f"{moment.hour:02d}:{moment.minute:02d}"


def format_when(start: datetime, end: datetime, all_day: bool, reader: Reader) -> str:
    """E.g. "Mon, Jan 7, 2030, 9:00 AM – 10:00 AM (Europe/Berlin)"; all-day ends are inclusive."""
    if all_day:
        first, last = as_utc(start).date(), as_utc(end).date()
        return _date(first, reader) if last <= first else f"{_date(first, reader)} – {_date(last, reader)}"
    tz = zone(reader.timezone)
    local_start, local_end = start.astimezone(tz), end.astimezone(tz)
    begin = f"{_date(local_start.date(), reader)}, {_time(local_start, reader)}"
    if local_end.date() == local_start.date() or local_end - local_start < timedelta(0):
        finish = _time(local_end, reader)
    else:
        finish = f"{_date(local_end.date(), reader)}, {_time(local_end, reader)}"
    return f"{begin} – {finish} ({reader.timezone})"


@dataclass
class When:
    """An event's time as an invitation shows it: a leaf of a tear-off calendar, the day written out and
    the time below it."""

    month: str
    day: int
    date: str
    time: str


def when_parts(start: datetime, end: datetime, all_day: bool, reader: Reader, all_day_text: str) -> When:
    """All-day ends are inclusive; an event over several days names both."""
    if all_day:
        first, last = as_utc(start).date(), as_utc(end).date()
        dates = (
            _long_date(first, reader) if last <= first else f"{_long_date(first, reader)} – {_long_date(last, reader)}"
        )
        return When(_tile_month(first, reader), first.day, dates, all_day_text)
    tz = zone(reader.timezone)
    local_start, local_end = start.astimezone(tz), end.astimezone(tz)
    tile = _tile_month(local_start.date(), reader), local_start.day
    if local_end.date() == local_start.date() or local_end - local_start < timedelta(0):
        return When(
            *tile,
            _long_date(local_start.date(), reader),
            f"{_time(local_start, reader)} – {_time(local_end, reader)} ({reader.timezone})",
        )
    return When(*tile, format_when(start, end, all_day, reader), "")


def _tile_month(day: date, reader: Reader) -> str:
    return _MONTHS[reader.language][day.month - 1].rstrip(".").upper()


# Messages -------------------------------------------------------------------------------------


@dataclass
class Link:
    label: str
    url: str
    # The main action, as a filled button; the others are outlined.
    primary: bool = False
    # Answers to invitations, outlined in the colour of the answer as on the invitation page.
    tone: Literal["accept", "tentative", "decline"] | None = None


# Light: border and text; the dark mode's text comes from _DARK_STYLE.
_TONES = {
    "accept": ("#16a34a", "#15803d"),
    "tentative": ("#f59e0b", "#b45309"),
    "decline": ("#dc2626", "#b91c1c"),
}


_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

# Dark colours for the mail programs that follow the system (Apple Mail, Outlook for Mac and iOS,
# Thunderbird); they override the inline light ones, hence !important. Gmail and Outlook for Windows
# ignore this and darken the light colours themselves.
_DARK_STYLE = (
    "@media (prefers-color-scheme: dark) {"
    ".mw-page { background:#111827 !important; }"
    ".mw-card { background:#1f2937 !important; border-color:#374151 !important; }"
    ".mw-heading, .mw-value { color:#f9fafb !important; }"
    ".mw-text { color:#d1d5db !important; }"
    ".mw-app, .mw-label { color:#9ca3af !important; }"
    ".mw-box { background:#1f2937 !important; border-color:#374151 !important; }"
    ".mw-button { background:#1f2937 !important; border-color:#4b5563 !important; color:#f9fafb !important; }"
    ".mw-footer { color:#6b7280 !important; }"
    ".mw-footer a { color:#9ca3af !important; }"
    ".mw-tone { background:#1f2937 !important; }"
    ".mw-notice-danger { background:#450a0a !important; color:#fecaca !important; }"
    ".mw-notice-warning { background:#422006 !important; color:#fde68a !important; }"
    ".mw-notice-success { background:#052e16 !important; color:#bbf7d0 !important; }"
    ".mw-notice-neutral { background:#111827 !important; color:#d1d5db !important; }"
    ".mw-before { color:#6b7280 !important; }"
    ".mw-band { background:#111827 !important; border-color:#374151 !important; }"
    ".mw-rule, .mw-tile { border-color:#374151 !important; }"
    ".mw-tone-accept { color:#4ade80 !important; }"
    ".mw-tone-tentative { color:#fbbf24 !important; }"
    ".mw-tone-decline { color:#f87171 !important; }"
    "}"
)


_LAYOUTS = {
    # In a row of buttons, centred, which wraps on narrow screens.
    "inline": "display:inline-block;margin:0 4px 8px;padding:10px 18px",
    # Filling a table cell, for buttons side by side in equal widths: little padding, so three of them
    # still fit side by side on a phone.
    "block": "display:block;margin:0;text-align:center;padding:10px 2px",
    "alone": "display:inline-block;margin:0;padding:10px 18px",
}


def _button(link: Link, layout: Literal["inline", "block", "alone"] = "inline") -> str:
    # The filled blue button reads well on both, so only outlined ones change in the dark.
    if link.primary:
        colors, css_class = "background:#2563eb;border:1px solid #2563eb;color:#ffffff", ""
    elif link.tone:
        border, color = _TONES[link.tone]
        colors = f"background:#ffffff;border:1.5px solid {border};color:{color}"
        css_class = f' class="mw-tone mw-tone-{link.tone}"'
    else:
        colors, css_class = "background:#ffffff;border:1px solid #d1d5db;color:#111827", ' class="mw-button"'
    return (
        f'<a href="{escape(link.url)}"{css_class} style="{_LAYOUTS[layout]};'
        f'border-radius:8px;{colors};font-size:14px;font-weight:600;line-height:20px;text-decoration:none">'
        f"{escape(link.label)}</a>"
    )


# A line on top of an event card: its background and text, light.
NoticeTone = Literal["danger", "warning", "success", "neutral"]
_NOTICE_TONES: dict[str, tuple[str, str]] = {
    "danger": ("#fef2f2", "#b91c1c"),
    "warning": ("#fffbeb", "#b45309"),
    "success": ("#f0fdf4", "#15803d"),
    "neutral": ("#f3f4f6", "#374151"),
}


@dataclass
class EventCard:
    """An email about an event laid out like the event's page in the app: what it is about, the title, a
    leaf of a tear-off calendar with the day and time beside it, place and organizer, the description,
    then the answers in a band of their own."""

    kicker: str
    title: str
    when: When
    repeats: str = ""
    # Labelled lines: place, organizer, resource, ...
    rows: Sequence[tuple[str, str]] = ()
    description: str = ""
    # What happened, in a coloured line on top: called off, changed, approved, an answer.
    notice: str = ""
    notice_tone: NoticeTone = "danger"
    # Called off: the title struck through.
    struck: bool = False
    # What a change replaced, shown struck through under the new value: by "title", "when",
    # "description" or the label of a row.
    previous: Mapping[str, str] = field(default_factory=dict)
    answers_heading: str = ""
    answers_hint: str = ""
    answers: Sequence[Link] = ()
    invited_as: str = ""
    view: Link | None = None


_SMALL = "font-size:14px;line-height:20px"
# Long words (addresses, links) break rather than widen the email beyond a phone's screen.
_WRAP = "overflow-wrap:anywhere;word-break:break-word"


def _before(value: str) -> str:
    """What a change replaced, struck through."""
    return (
        f'<div class="mw-before" style="color:#9ca3af;text-decoration:line-through;white-space:pre-line;{_WRAP}">'
        f"{escape(value or '—')}</div>"
    )


def _card_html(card: EventCard) -> str:
    out = []
    if card.notice:
        background, color = _NOTICE_TONES[card.notice_tone]
        out.append(
            f'<div class="mw-notice mw-notice-{card.notice_tone}" style="padding:12px 28px;background:{background};'
            f'color:{color};font-size:14px;font-weight:600;border-radius:12px 12px 0 0;{_WRAP}">'
            f"{escape(card.notice)}</div>"
        )
    title_style = "text-decoration:line-through;opacity:0.6;" if card.struck else ""
    tile = (
        '<table class="mw-tile" role="presentation" cellpadding="0" cellspacing="0" width="56" '
        'style="width:56px;border:1px solid #e5e7eb;border-radius:8px;border-collapse:separate">'
        '<tr><td style="padding:2px 0;background:#2563eb;border-radius:7px 7px 0 0;color:#ffffff;font-size:11px;'
        f'font-weight:600;line-height:16px;text-align:center;letter-spacing:0.05em">{escape(card.when.month)}</td></tr>'
        '<tr><td class="mw-heading" style="padding:4px 0;color:#111827;font-size:20px;font-weight:600;'
        f'line-height:28px;text-align:center">{card.when.day}</td></tr></table>'
    )
    when_lines = [f'<div class="mw-value" style="color:#111827;font-weight:600;{_WRAP}">{escape(card.when.date)}</div>']
    when_lines += [
        f'<div class="mw-text" style="color:#4b5563;{_WRAP}">{escape(line)}</div>'
        for line in (card.when.time, card.repeats)
        if line
    ]
    if "when" in card.previous:
        when_lines.append(_before(card.previous["when"]))
    rows = "".join(
        '<tr><td class="mw-label" style="padding:3px 16px 3px 0;color:#6b7280;vertical-align:top;white-space:nowrap">'
        f"{escape(label)}</td>"
        f'<td class="mw-value" style="padding:3px 0;color:#111827;vertical-align:top;{_WRAP}">{escape(value)}'
        f"{_before(card.previous[label]) if label in card.previous else ''}</td></tr>"
        for label, value in card.rows
    )
    old_title = card.previous.get("title")
    heading = (
        f'<h1 class="mw-heading" style="margin:4px 0 {0 if old_title is not None else 20}px;color:#111827;'
        f'font-size:24px;font-weight:600;line-height:32px;{title_style}{_WRAP}">{escape(card.title)}</h1>'
    )
    if old_title is not None:
        heading += f'<div style="margin:0 0 20px">{_before(old_title)}</div>'
    main = [
        '<p class="mw-label" style="margin:0;color:#6b7280;font-size:12px;font-weight:600;line-height:16px;'
        f'letter-spacing:0.05em;text-transform:uppercase;{_WRAP}">{escape(card.kicker)}</p>',
        heading,
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="{_SMALL}"><tr>'
        f'<td style="vertical-align:top;padding-right:16px">{tile}</td>'
        f'<td style="vertical-align:top">{"".join(when_lines)}</td></tr></table>',
    ]
    if rows:
        main.append(
            '<table role="presentation" cellpadding="0" cellspacing="0" '
            f'style="margin-top:20px;{_SMALL}">{rows}</table>'
        )
    if card.description:
        main.append(
            '<div class="mw-rule mw-text" style="margin-top:20px;padding-top:20px;border-top:1px solid #e5e7eb;'
            f'color:#374151;white-space:pre-line;{_SMALL};{_WRAP}">{escape(card.description)}'
            f"{_before(card.previous['description']) if 'description' in card.previous else ''}</div>"
        )
    out.append(f'<div style="padding:28px">{"".join(main)}</div>')

    if card.answers:
        width = f"{100 // len(card.answers)}%"
        cells = "".join(
            f'<td width="{width}" style="padding:0 {4 if i < len(card.answers) - 1 else 0}px 0 {4 if i else 0}px">'
            f"{_button(link, 'block')}</td>"
            for i, link in enumerate(card.answers)
        )
        hint = (
            f'<p class="mw-label" style="margin:12px 0 0;color:#6b7280;font-size:12px;line-height:16px">'
            f"{escape(card.answers_hint)}</p>"
            if card.answers_hint
            else ""
        )
        out.append(
            '<div class="mw-band" style="padding:20px 28px;background:#f9fafb;border-top:1px solid #e5e7eb">'
            f'<p class="mw-heading" style="margin:0 0 12px;color:#374151;font-size:14px;font-weight:600">'
            f"{escape(card.answers_heading)}</p>"
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{cells}</tr></table>'
            f"{hint}</div>"
        )
    if card.invited_as or card.view:
        # One below the other: side by side, a long address would make the email wider than a phone.
        view = f'<div style="margin:0 0 8px">{_button(card.view, "alone")}</div>' if card.view else ""
        invited = (
            f'<div class="mw-label" style="color:#6b7280;font-size:12px;line-height:16px;{_WRAP}">'
            f"{escape(card.invited_as)}</div>"
            if card.invited_as
            else ""
        )
        out.append(
            '<div class="mw-rule" style="padding:16px 28px;border-top:1px solid #e5e7eb;text-align:center">'
            f"{view}{invited}</div>"
        )
    return "".join(out)


def _html(
    subject: str,
    heading: str | None,
    paragraphs: list[str],
    details: Sequence[tuple[str, str]],
    links: Sequence[Link],
    footer: Footer,
    app: str,
    language: str,
    logo_src: str | None,
    card: EventCard | None = None,
) -> str:
    """The HTML part, with tables and inline styles as mail programs need: heading, paragraphs, details
    and buttons, or for an email about an event its card (`card`) instead."""
    body = []
    if heading:
        body.append(
            '<h1 class="mw-heading" '
            f'style="margin:0 0 12px;font-size:20px;line-height:28px;font-weight:600;color:#111827;{_WRAP}">'
            f"{escape(heading)}</h1>"
        )
    body += [
        f'<p class="mw-text" style="margin:0 0 12px;font-size:15px;line-height:22px;color:#374151;{_WRAP}">'
        f"{escape(p)}</p>"
        for p in paragraphs
    ]
    if details:
        rows = "".join(
            '<tr><td class="mw-label" '
            'style="padding:4px 16px 4px 0;color:#6b7280;vertical-align:top;white-space:nowrap">'
            f"{escape(label)}</td>"
            f'<td class="mw-value" style="padding:4px 0;color:#111827;vertical-align:top;white-space:pre-line;{_WRAP}">'
            f"{escape(value)}</td></tr>"
            for label, value in details
        )
        body.append(
            '<table class="mw-box" role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="margin:8px 0 20px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px">'
            f'<tr><td style="padding:12px 16px"><table role="presentation" cellpadding="0" cellspacing="0" '
            f'style="font-size:14px;line-height:20px">{rows}</table></td></tr></table>'
        )
    header = escape(app)
    if logo_src:
        header = (
            f'<img src="{escape(logo_src)}" width="32" height="32" alt="" '
            'style="display:inline-block;width:32px;height:32px;margin-right:10px;border:0;border-radius:7px;'
            f'vertical-align:middle">{header}'
        )
    for group in ([link for link in links if link.primary], [link for link in links if not link.primary]):
        if group:
            body.append(
                f'<div style="margin:8px 0 0;text-align:center">{"".join(_button(link) for link in group)}</div>'
            )

    # One layout at every width: the page itself, with the app on top and the footer below, each set off
    # by a rule; an event comes as a card of its own (the frame is not a card, so a phone doesn't get the
    # margins twice).
    content = (
        '<div class="mw-card" style="background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;'
        f'overflow:hidden">{_card_html(card)}</div>'
        if card
        else "".join(body)
    )
    return (
        f'<!DOCTYPE html><html lang="{language}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">'
        f"<title>{escape(subject)}</title><style>:root {{ color-scheme: light dark; }} {_DARK_STYLE}</style></head>"
        f'<body class="mw-page" style="margin:0;padding:0;background:#ffffff;font-family:{_FONT}">'
        '<table class="mw-page" role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#ffffff">'
        '<tr><td align="center" style="padding:24px 16px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px">'
        '<tr><td class="mw-app mw-rule" style="padding:0 0 16px;border-bottom:1px solid #e5e7eb;'
        f'font-family:{_FONT};font-size:15px;font-weight:600;color:#374151">{header}</td></tr>'
        f'<tr><td style="padding:24px 0;font-family:{_FONT}">{content}</td></tr>'
        '<tr><td class="mw-footer mw-rule" style="padding:16px 0 0;border-top:1px solid #e5e7eb;'
        f'font-family:{_FONT};font-size:12px;line-height:18px;color:#9ca3af">{_footer_html(footer)}</td></tr>'
        "</table></td></tr></table></body></html>"
    )


@dataclass
class Footer:
    """What every email ends with: who it went to and why, then links (email settings, unsubscribing
    from this kind, the app)."""

    sent_to: str
    reason: str
    links: Sequence[Link] = ()


def _footer_html(footer: Footer) -> str:
    links = " &nbsp;·&nbsp; ".join(
        f'<a href="{escape(link.url)}" style="color:#6b7280;text-decoration:underline">{escape(link.label)}</a>'
        for link in footer.links
    )
    return f'<p style="margin:0;{_WRAP}">{escape(footer.sent_to)} {escape(footer.reason)}</p>' + (
        f'<p style="margin:8px 0 0">{links}</p>' if links else ""
    )


def _footer(
    to: str, reason: str, language: str, app: str, recipient: User | None, kind: str | None, event: Event | None
) -> tuple[Footer, dict[str, str]]:
    """The footer, and the headers that let mail programs offer to unsubscribe (RFC 2369, 8058).

    Settings and unsubscribing are for a kind users can switch off (`kind`); people without an account
    (guests invited to an event) get neither, nor the way into the app.
    """
    links: list[Link] = []
    headers: dict[str, str] = {}
    if recipient is not None and kind is not None:
        token = make_token(recipient, kind)
        links.append(Link(text(language, "footer_settings_link"), f"{settings.APP_URL}/account?tab=emailNotifications"))
        if event is not None:
            event_token = make_token(recipient, event=event)
            links.append(Link(text(language, "footer_mute_event"), f"{settings.APP_URL}/unsubscribe/{event_token}"))
        label = text(language, "footer_unsubscribe_kind" if event is not None else "footer_unsubscribe")
        links.append(Link(label, f"{settings.APP_URL}/unsubscribe/{token}"))
        headers["List-Unsubscribe"] = f"<{settings.APP_URL}/api/unsubscribe/{token}>"
        headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    if recipient is not None:
        links.append(Link(text(language, "footer_home", app=app), f"{settings.APP_URL}/"))
    return Footer(text(language, "sent_to", email=to), reason, links), headers


def build_message(
    to: str,
    subject: str,
    paragraphs: list[str],
    language: str,
    reason: str,
    details: Sequence[tuple[str, str]] = (),
    links: Sequence[Link] = (),
    from_name: str | None = None,
    reply_to: str | None = None,
    app: str | None = None,
    heading: str | None = None,
    card: EventCard | None = None,
    recipient: User | None = None,
    kind: str | None = None,
    event: Event | None = None,
) -> EmailMultiAlternatives:
    """A plain-text and HTML email: a heading, paragraphs, then labelled details, then links as buttons,
    and the footer: who it went to, why (`reason`), and for an account (`recipient`) the way into the
    app, and for a kind of email they can switch off (`kind`) their settings and unsubscribing; for an
    email about an event (`event`, a series as a whole), also from the emails about it.

    `app`: the app's name, when the caller has it already (it's looked up otherwise).
    """
    app = app or app_name()
    footer, headers = _footer(to, reason, language, app, recipient, kind, event)
    subject = one_line(subject)
    plain = ["\n\n".join(paragraphs)]
    if details:
        plain.append("\n".join(f"{label}: {value}" for label, value in details))
    if links:
        plain.append("\n".join(f"{link.label}: {link.url}" for link in links))
    footer_links = [f"{link.label}: {link.url}" for link in footer.links]
    plain.append("\n".join([f"-- \n{footer.sent_to} {footer.reason}", *footer_links]))

    message = Message(
        subject=subject,
        body="\n\n".join(plain) + "\n",
        from_email=sender(from_name, app),
        to=[to],
        reply_to=[reply_to] if reply_to else None,
        headers=headers or None,
    )
    shown = logo()
    if isinstance(shown, InlineImage):
        message.logo = shown
        shown = f"cid:{LOGO_CID}"
    html = _html(subject, heading, paragraphs, details, links, footer, app, language, shown, card)
    message.attach_alternative(html, "text/html")
    return message


def _add_logo(msg: email.message.EmailMessage, logo: InlineImage) -> None:
    """Puts the logo the HTML shows (cid:) in a multipart/related around all the alternatives, as Apple
    Mail sends it, not around the HTML alone: next to an invitation's calendar data, Apple Mail and
    Thunderbird take only an HTML part right beside it for the email to show."""
    image = email.message.MIMEPart(policy=msg.policy)
    image.set_content(
        logo.data,
        maintype="image",
        subtype=logo.subtype,
        cid=f"<{LOGO_CID}>",
        disposition="inline",
        filename=f"logo.{logo.subtype}",
    )
    related_type = 'multipart/related; type="multipart/alternative"'
    alternatives = next(part for part in msg.walk() if part.get_content_type() == "multipart/alternative")
    if alternatives is msg:
        # Without attachments the alternatives are the message itself: they move into its first part.
        inner = email.message.MIMEPart(policy=msg.policy)
        inner["Content-Type"] = msg["Content-Type"]
        inner.set_payload(msg.get_payload())
        del msg["Content-Type"]
        msg["Content-Type"] = related_type
        msg.set_payload([inner, image])
        return
    related = email.message.MIMEPart(policy=msg.policy)
    related["Content-Type"] = related_type
    related.set_payload([alternatives, image])
    parent = next(
        part for part in msg.walk() if part.is_multipart() and any(p is alternatives for p in part.get_payload())
    )
    siblings = parent.get_payload()
    assert isinstance(siblings, list)  # a multipart's payload is its parts
    parent.set_payload([related if p is alternatives else p for p in siblings])


class Message(EmailMultiAlternatives):
    """An email whose HTML part may come with the logo it shows (cid:), and whose unsubscribe header
    stays readable."""

    logo: InlineImage | None = None

    def message(self, *, policy: Policy | None = email.policy.default) -> email.message.EmailMessage:
        if "List-Unsubscribe" in self.extra_headers:
            # Its URL is longer than the 78 characters a line should have, and has no space to fold
            # at: the default would encode it (=?utf-8?q?...), which mail programs don't read as an
            # address, so they wouldn't offer to unsubscribe. Lines may have up to 998 (RFC 5322).
            policy = (policy or email.policy.default).clone(max_line_length=998)
        msg = super().message(policy=policy)
        if self.logo is not None:
            _add_logo(msg, self.logo)
        return msg


# Sending --------------------------------------------------------------------------------------


def deliver(messages: list[EmailMultiAlternatives]) -> None:
    """Hands the messages to the mail server; raises if that fails."""
    get_connection().send_messages(messages)


def _deliver_logging_failures(messages: list[EmailMultiAlternatives]) -> None:
    try:
        deliver(messages)
    except Exception:
        logger.exception("Sending %d email(s) failed", len(messages))


def _after_commit(callback: Callable[[], object]) -> None:
    transaction.on_commit(callback)


def send(messages: Iterable[EmailMultiAlternatives | None]) -> None:
    """Sends the messages if the current transaction commits.

    With EMAIL_SEND_IN_BACKGROUND, each becomes a job (apps.core.jobs.defer: in the task queue, saved in
    the transaction; natively run right after it); otherwise they go out right after it, and a
    failure is only logged.
    """
    to_send = [m for m in messages if m is not None]
    if not to_send:
        return
    if settings.EMAIL_SEND_IN_BACKGROUND:
        from apps.core.tasks import send_email  # apps.core.tasks uses this module

        for message in to_send:
            jobs.defer(send_email, message=message_data(message))
    else:
        _after_commit(lambda: _deliver_logging_failures(to_send))


def message_data(message: EmailMultiAlternatives) -> dict[str, Any]:
    """The message as JSON, for a job of the task queue; message_from_data() reads it."""
    return {
        "subject": message.subject,
        "body": message.body,
        "from_email": message.from_email,
        "to": message.to,
        "reply_to": message.reply_to,
        "headers": message.extra_headers,
        "alternatives": [[content, mimetype] for content, mimetype in message.alternatives],
        "attachments": [[name, content, mimetype] for name, content, mimetype in message.attachments],
        "logo": _logo_data(message),
    }


def _logo_data(message: EmailMultiAlternatives) -> list[str] | None:
    image = message.logo if isinstance(message, Message) else None
    return [base64.b64encode(image.data).decode(), image.subtype] if image else None


def message_from_data(data: dict[str, Any]) -> EmailMultiAlternatives:
    message = Message(
        subject=data["subject"],
        body=data["body"],
        from_email=data["from_email"],
        to=data["to"],
        reply_to=data["reply_to"],
        # Jobs saved before emails carried headers (unsubscribing) have none.
        headers=data.get("headers") or None,
    )
    for content, mimetype in data["alternatives"]:
        message.attach_alternative(content, mimetype)
    for name, content, mimetype in data["attachments"]:
        message.attach(name, content, mimetype)
    # Jobs saved before emails carried the logo have none.
    if data.get("logo"):
        content, subtype = data["logo"]
        message.logo = InlineImage(base64.b64decode(content), subtype)
    return message
