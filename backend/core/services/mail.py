"""
Sending emails: notifications and invitations.

Messages are built during the request (from the data as it is then) and go out as jobs of the task
queue (core.tasks), which are saved along with the request's changes: a slow or unreachable mail
server neither holds up nor fails the request, and the worker tries again until it takes them.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.utils import formataddr
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction

from core.models.users import User, get_or_create_app_settings
from core.services.mail_texts import text
from core.services.recurrence import as_utc, zone

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
    app: str | None = None,
) -> EmailMultiAlternatives:
    """A plain-text and HTML email: paragraphs, then labelled details, then links as buttons.

    `app`: the app's name, when the caller has it already (it's looked up otherwise).
    """
    app = app or app_name()
    footer = text(language, footer, app=app)
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
        subject=one_line(subject),
        body="\n\n".join(plain) + "\n",
        from_email=sender(from_name, app),
        to=[to],
        reply_to=[reply_to] if reply_to else None,
    )
    message.attach_alternative(
        f'<div style="font-family:system-ui,sans-serif;font-size:14px;color:#111827">{"".join(html)}</div>',
        "text/html",
    )
    return message


# Sending --------------------------------------------------------------------------------------


def deliver(messages: list[EmailMultiAlternatives]) -> None:
    """Hands the messages to the mail server; raises if that fails."""
    get_connection().send_messages(messages)


def _deliver_logging_failures(messages: list[EmailMultiAlternatives]) -> None:
    try:
        deliver(messages)
    except Exception:
        logger.exception("Sending %d email(s) failed", len(messages))


def _after_commit(callback) -> None:
    transaction.on_commit(callback)


def send(messages) -> None:
    """Sends the messages if the current transaction commits.

    With EMAIL_SEND_IN_BACKGROUND, each becomes a job of the task queue, saved in the transaction;
    otherwise they go out right after it, and a failure is only logged.
    """
    messages = [m for m in messages if m is not None]
    if not messages:
        return
    if settings.EMAIL_SEND_IN_BACKGROUND:
        from core.tasks import send_email  # core.tasks uses this module

        for message in messages:
            send_email.defer(message=message_data(message))
    else:
        _after_commit(lambda: _deliver_logging_failures(messages))


def message_data(message: EmailMultiAlternatives) -> dict:
    """The message as JSON, for a job of the task queue; message_from_data() reads it."""
    return {
        "subject": message.subject,
        "body": message.body,
        "from_email": message.from_email,
        "to": message.to,
        "reply_to": message.reply_to,
        "alternatives": [[content, mimetype] for content, mimetype in message.alternatives],
        "attachments": [[name, content, mimetype] for name, content, mimetype in message.attachments],
    }


def message_from_data(data: dict) -> EmailMultiAlternatives:
    message = EmailMultiAlternatives(
        subject=data["subject"],
        body=data["body"],
        from_email=data["from_email"],
        to=data["to"],
        reply_to=data["reply_to"],
    )
    for content, mimetype in data["alternatives"]:
        message.attach_alternative(content, mimetype)
    for name, content, mimetype in data["attachments"]:
        message.attach(name, content, mimetype)
    return message
