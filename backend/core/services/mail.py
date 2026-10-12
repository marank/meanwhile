"""
Sending emails: notifications and invitations.

Messages are built during the request (from the data as it is then) and go out once its
transaction has committed, in a background thread, so a slow or unreachable mail server neither
holds up nor fails the request. Failures are logged.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.utils import formataddr
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction

from core.models.users import User, get_or_create_app_settings
from core.services.mail_texts import text
from core.services.recurrence import make_aware, zone

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mail")


def app_name() -> str:
    return get_or_create_app_settings().app_name or "Calendar"


def sender(name: str | None = None) -> str:
    """The From address: the app's address, under the name of whoever acts, if anyone."""
    app = app_name()
    return formataddr((f"{name} ({app})" if name else app, settings.DEFAULT_FROM_EMAIL))


def language_of(user: User | None, fallback: str = "en") -> str:
    language = (user.language if user else "") or fallback
    return language if language in ("en", "de") else "en"


def app_link(path: str) -> str | None:
    """An absolute link into the app, if its address is known."""
    return f"{settings.APP_URL}{path}" if settings.APP_URL else None


# Times ----------------------------------------------------------------------------------------

_WEEKDAYS = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "de": ["Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."],
}
_MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "de": ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sep.", "Okt.", "Nov.", "Dez."],
}


@dataclass
class Reader:
    """How a recipient reads times: language, zone and clock."""

    language: str = "en"
    timezone: str = "UTC"
    twelve_hour: bool = False

    @classmethod
    def of(cls, user: User | None, language: str, timezone: str) -> "Reader":
        clock = user.time_format if user else "auto"
        twelve = clock == "12h" or (clock == "auto" and language == "en")
        return cls(language, (user.timezone if user else "") or timezone or "UTC", twelve)


def _date(day: date, reader: Reader) -> str:
    weekday = _WEEKDAYS[reader.language][day.weekday()]
    month = _MONTHS[reader.language][day.month - 1]
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
        first, last = make_aware(start).date(), make_aware(end).date()
        return _date(first, reader) if last <= first else f"{_date(first, reader)} – {_date(last, reader)}"
    tz = zone(reader.timezone)
    local_start, local_end = make_aware(start).astimezone(tz), make_aware(end).astimezone(tz)
    begin = f"{_date(local_start.date(), reader)}, {_time(local_start, reader)}"
    if local_end.date() == local_start.date() or local_end - local_start < timedelta(0):
        finish = _time(local_end, reader)
    else:
        finish = f"{_date(local_end.date(), reader)}, {_time(local_end, reader)}"
    return f"{begin} – {finish} ({reader.timezone})"


# Messages -------------------------------------------------------------------------------------


@dataclass
class Link:
    label: str
    url: str


def build_message(
    to: str,
    subject: str,
    paragraphs: list[str],
    language: str,
    details: list[tuple[str, str]] = (),
    links: list[Link] = (),
    from_name: str | None = None,
    reply_to: str | None = None,
    footer: str = "footer",
) -> EmailMultiAlternatives:
    """A plain-text and HTML email: paragraphs, then labelled details, then links as buttons."""
    footer = text(language, footer, app=app_name())
    plain = ["\n\n".join(paragraphs)]
    if details:
        plain.append("\n".join(f"{label}: {value}" for label, value in details))
    if links:
        plain.append("\n".join(f"{link.label}: {link.url}" for link in links))
    plain.append(f"-- \n{footer}")

    html = [f"<p>{escape(p)}</p>" for p in paragraphs]
    if details:
        rows = "".join(
            f'<tr><td style="padding:2px 12px 2px 0;color:#6b7280;vertical-align:top">{escape(label)}</td>'
            f'<td style="padding:2px 0;white-space:pre-line">{escape(value)}</td></tr>'
            for label, value in details
        )
        html.append(f"<table style=\"border-collapse:collapse;margin:12px 0\">{rows}</table>")
    if links:
        buttons = " ".join(
            f'<a href="{escape(link.url)}" style="display:inline-block;margin:4px 8px 4px 0;padding:8px 14px;'
            f'border-radius:8px;background:#2563eb;color:#fff;text-decoration:none">{escape(link.label)}</a>'
            for link in links
        )
        html.append(f"<p>{buttons}</p>")
    html.append(f'<p style="margin-top:24px;color:#9ca3af;font-size:12px">{escape(footer)}</p>')

    message = EmailMultiAlternatives(
        subject=subject,
        body="\n\n".join(plain) + "\n",
        from_email=sender(from_name),
        to=[to],
        reply_to=[reply_to] if reply_to else None,
    )
    message.attach_alternative(
        f'<div style="font-family:system-ui,sans-serif;font-size:14px;color:#111827">{"".join(html)}</div>',
        "text/html",
    )
    return message


# Sending --------------------------------------------------------------------------------------


def _send_now(messages: list[EmailMultiAlternatives]) -> None:
    try:
        get_connection().send_messages(messages)
    except Exception:
        logger.exception("Sending %d email(s) failed", len(messages))


def _after_commit(callback) -> None:
    transaction.on_commit(callback)


def send(messages) -> None:
    """Sends the messages once the current transaction has committed; not at all if it fails."""
    messages = [m for m in messages if m is not None]
    if not messages:
        return

    def dispatch():
        if settings.EMAIL_SEND_IN_BACKGROUND:
            _executor.submit(_send_now, messages)
        else:
            _send_now(messages)

    _after_commit(dispatch)
