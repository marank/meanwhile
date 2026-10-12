"""
Scheduling by email: iTIP messages (RFC 5546) sent and received as iMIP (RFC 6047).

Participants get the event as REQUEST when invited and whenever it changes, and a CANCEL when it
is deleted, cancelled or rejected, or when they are taken off it. Any mail program can show and
answer these. The answers (REPLY) go to the event's organizer address: the app's own mailbox
(IMIP_ADDRESS) when there is one, which `fetch_imip` reads; otherwise the organizer's own address.
The invitation also carries links to answer in the browser, for participants without such a mail
program and in development.

Only changes made in the app are sent. CalDAV clients that change events schedule by themselves
(e.g. Thunderbird sends its own invitations), so the app doesn't send a second set.
"""

import email
import email.policy
import imaplib
import logging
from datetime import datetime
from email.utils import getaddresses

import icalendar
from django.conf import settings
from django.utils import timezone

from core.models import Event, EventParticipant
from core.models.base import EventStatus
from core.services import mail
from core.services.ical import PARTSTAT, SCHEDULING, build_series_ical, new_calendar, to_ical
from core.services.mail_texts import text
from core.services.notifications import notify, wants_email
from core.services.recurrence import as_utc

logger = logging.getLogger(__name__)

_GONE = {EventStatus.REJECTED, EventStatus.CANCELLED}
_ANSWERS = {value: key for key, value in PARTSTAT.items()}


def series_of(event: Event) -> Event:
    return event.parent if event.parent_id else event


def _recipients(series: Event, only: list[EventParticipant] | None = None) -> list[EventParticipant]:
    """The participants to send to: the series' and its changed occurrences', once per address.

    Leaves out the organizer, and users who don't want invitations by email (they have them in
    the app).
    """
    if only is not None:
        candidates = list(only)
    else:
        candidates = list(series.participants.select_related("user"))
        for override in series.overrides.all():
            candidates += list(override.participants.select_related("user"))
    organizer = series.creator.email.lower()
    found, seen = [], set()
    for participant in candidates:
        address = participant.email.lower()
        if address in seen or address == organizer:
            continue
        seen.add(address)
        if participant.user is not None and not wants_email(participant.user, "invitations"):
            continue
        found.append(participant)
    return found


def bump_sequence(series: Event) -> None:
    """Counts a change participants are sent, so their programs replace what they have."""
    series.sequence += 1
    series.save(update_fields=["sequence", "updated_at"])


# Outgoing -------------------------------------------------------------------------------------


def request_ical(series: Event) -> str:
    cal = new_calendar("REQUEST")
    for component in build_series_ical(series, audience=SCHEDULING):
        cal.add_component(component)
    return to_ical(cal)


def cancel_ical(series: Event, participants: list[EventParticipant], sequence: int) -> str:
    """CANCEL of the whole event, naming the participants it is sent to."""
    vevent = build_series_ical(series, audience=SCHEDULING)[0]
    for name in ("STATUS", "ATTENDEE", "SEQUENCE", "DTSTAMP"):
        vevent.pop(name, None)
    vevent.add("status", "CANCELLED")
    vevent.add("sequence", sequence)
    vevent.add("dtstamp", timezone.now())
    for participant in participants:
        vevent.add("attendee", icalendar.vCalAddress(f"mailto:{participant.email}"))
    cal = new_calendar("CANCEL")
    cal.add_component(vevent)
    return to_ical(cal)


def _message(series: Event, participant: EventParticipant, method: str, ical_text: str, kind: str):
    """`kind`: "invite", "update", "cancel" or "removed"."""
    organizer = series.creator
    language = mail.language_of(participant.user, fallback=mail.language_of(organizer))
    reader = mail.Reader.of(participant.user, language, series.timezone)
    title = series.title or text(language, "untitled")
    when = mail.format_when(series.start, series.end, series.all_day, reader)
    name = organizer.display_name or organizer.email

    subject_kind = "cancel" if kind == "removed" else kind
    paragraphs = [text(language, f"{kind}_body", organizer=name, title=title)]
    details = [(text(language, "when"), when)]
    if series.location:
        details.append((text(language, "location"), series.location))
    details.append((text(language, "organizer"), f"{name} <{organizer.email}>"))
    if series.description and method == "REQUEST":
        details.append((text(language, "description"), series.description))

    links = []
    if method == "REQUEST":
        paragraphs.append(text(language, "rsvp_prompt"))
        for answer, label in (("accepted", "accept"), ("tentative", "tentative"), ("declined", "decline")):
            url = mail.app_link(f"/rsvp/{participant.rsvp_token}?answer={answer}")
            if url:
                links.append(mail.Link(text(language, label), url))

    message = mail.build_message(
        to=participant.email,
        subject=text(language, f"{subject_kind}_subject", title=title, when=when),
        paragraphs=paragraphs,
        language=language,
        details=details,
        links=links,
        from_name=name,
        reply_to=organizer.email,
    )
    # Inline for mail programs that show invitations, and as file for those that don't.
    message.attach_alternative(ical_text, f"text/calendar; method={method}")
    message.attach("invite.ics", ical_text, "application/ics")
    return message


def send_request(event: Event, participants: list[EventParticipant] | None = None, update: bool = False) -> None:
    """Sends the event as it is now to its participants (or those given).

    `update`: the event changed; counts the change and says so.
    """
    series = series_of(event)
    if series.status in _GONE:
        return
    recipients = _recipients(series, participants)
    if update:
        bump_sequence(series)
    if not recipients:
        return
    ical_text = request_ical(series)
    kind = "update" if update else "invite"
    mail.send(_message(series, p, "REQUEST", ical_text, kind) for p in recipients)


def send_cancel(event: Event, participants: list[EventParticipant] | None = None) -> None:
    """Tells participants (all, or those given and taken off it) that the event doesn't take place.

    Call it before deleting the event: the message is built from the event as it still is.
    """
    series = series_of(event)
    recipients = _recipients(series, participants)
    if not recipients:
        return
    bump_sequence(series)
    ical_text = cancel_ical(series, recipients, series.sequence)
    kind = "removed" if participants is not None else "cancel"
    mail.send(_message(series, p, "CANCEL", ical_text, kind) for p in recipients)


# Answers --------------------------------------------------------------------------------------


def record_answer(participant: EventParticipant, status: str, name: str | None = None) -> bool:
    """A participant's own answer, from the app, the link in the invitation or their mail program.

    An answer for a series holds for its changed occurrences too. Tells the organizer.
    """
    if participant.status == status:
        return False
    participant.status = status
    participant.save()
    event = participant.event
    if not event.parent_id:
        for other in EventParticipant.objects.filter(event__parent=event, email__iexact=participant.email):
            if other.status != status:
                other.status = status
                other.save()
    series = series_of(event)
    who = participant.user
    notify(
        [str(series.creator_id)],
        "participant_replied",
        str(who.id) if who else None,
        series.title or "",
        calendar_id=str(series.calendar_id),
        event_id=str(event.id),
        data={"status": status, "email": participant.email, "name": (who.display_name if who else name) or None},
    )
    return True


def _address(value) -> str:
    return str(value or "").strip().lower().removeprefix("mailto:")


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _reply(vevent, sender: str | None) -> list[str]:
    uid = str(vevent.get("UID", ""))
    rid = vevent.get("RECURRENCE-ID")
    occurrence = None
    if rid is not None:
        value = rid.dt
        occurrence = as_utc(value if isinstance(value, datetime) else datetime(value.year, value.month, value.day))
    results = []
    for attendee in _as_list(vevent.get("ATTENDEE")):
        address = _address(attendee)
        params = getattr(attendee, "params", {})
        status = _ANSWERS.get(str(params.get("PARTSTAT", "")).upper())
        if status is None:
            results.append(f"{uid}: {address}: unsupported answer {params.get('PARTSTAT')!r}")
            continue
        # Only the participant answers for themselves (or whoever they let send for them).
        if sender is not None and sender not in (address, _address(params.get("SENT-BY"))):
            results.append(f"{uid}: {address}: ignored, sent by {sender}")
            continue
        participants = EventParticipant.objects.select_related("event", "user").filter(
            event__uid=uid, email__iexact=address
        )
        participants = (
            participants.filter(event__parent__isnull=True)
            if occurrence is None
            else participants.filter(event__recurrence_id=occurrence)
        )
        found = list(participants)
        if not found:
            results.append(f"{uid}: {address}: no such invitation")
            continue
        for participant in found:
            changed = record_answer(participant, status, params.get("CN"))
            results.append(f"{uid}: {address}: {status}" + ("" if changed else " (unchanged)"))
    return results


def _refresh(vevent, sender: str | None) -> list[str]:
    """A participant asks for the event again."""
    uid = str(vevent.get("UID", ""))
    results = []
    for attendee in _as_list(vevent.get("ATTENDEE")):
        address = _address(attendee)
        if sender is not None and sender != address:
            continue
        for participant in EventParticipant.objects.select_related("event", "user").filter(
            event__uid=uid, event__parent__isnull=True, email__iexact=address
        ):
            send_request(participant.event, [participant])
            results.append(f"{uid}: {address}: sent again")
    return results


def process_itip(data: bytes | str, sender: str | None = None) -> list[str]:
    """Applies an iTIP message from `sender` (None: trusted, e.g. a file given by an admin)."""
    try:
        cal = icalendar.Calendar.from_ical(data)
    except Exception as exc:
        return [f"unreadable iCalendar: {exc}"]
    method = str(cal.get("METHOD", "")).upper()
    handler = {"REPLY": _reply, "REFRESH": _refresh}.get(method)
    if handler is None:
        return [f"method {method or 'none'} ignored"]
    results = []
    for vevent in cal.walk("VEVENT"):
        results += handler(vevent, sender)
    return results


def process_email(raw: bytes, trust_sender: bool = False) -> list[str]:
    """Applies the iTIP messages in an email; answers count only for the address that sent them."""
    message = email.message_from_bytes(raw, policy=email.policy.default)
    senders = getaddresses([str(message.get("From", ""))])
    sender = None if trust_sender else (senders[0][1].lower() if senders and senders[0][1] else "")
    seen, results = set(), []
    for part in message.walk():
        filename = (part.get_filename() or "").lower()
        if part.get_content_type() not in ("text/calendar", "application/ics") and not filename.endswith(".ics"):
            continue
        payload = part.get_payload(decode=True)
        # The same message often comes inline and as attachment.
        if not payload or payload in seen:
            continue
        seen.add(payload)
        results += process_itip(payload, sender)
    return results or ["no iTIP message found"]


def fetch_mailbox() -> list[str]:
    """Applies the unread messages in the iMIP mailbox (IMAP) and marks them read."""
    if not settings.IMIP_IMAP_HOST:
        raise RuntimeError("IMIP_IMAP_HOST is not set")
    connect = imaplib.IMAP4_SSL if settings.IMIP_IMAP_SSL else imaplib.IMAP4
    results = []
    with connect(settings.IMIP_IMAP_HOST, settings.IMIP_IMAP_PORT) as imap:
        imap.login(settings.IMIP_IMAP_USER, settings.IMIP_IMAP_PASSWORD)
        imap.select(settings.IMIP_IMAP_FOLDER)
        _, found = imap.search(None, "UNSEEN")
        for number in found[0].split():
            _, parts = imap.fetch(number, "(BODY.PEEK[])")
            raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
            try:
                results += process_email(raw) if raw else []
            except Exception:
                # Marked read all the same, so one broken message doesn't come back every time.
                logger.exception("Processing iMIP message %s failed", number)
            imap.store(number, "+FLAGS", "\\Seen")
    return results
