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
from collections.abc import Callable
from datetime import datetime
from email.message import Message
from email.utils import getaddresses
from typing import Any

import icalendar
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q, QuerySet
from django.utils import timezone

from core.models import Event, EventParticipant
from core.models.base import EventStatus
from core.services import mail
from core.services.ical import (
    PARTSTAT,
    SCHEDULING,
    build_event_ical,
    build_series_ical,
    new_calendar,
    replaced_start,
    to_ical,
)
from core.services.mail_texts import text
from core.services.notifications import notify, wants_email
from core.services.recurrence import as_utc, is_series
from core.services.series import is_occurrence, override_for

logger = logging.getLogger(__name__)

_GONE = {EventStatus.REJECTED, EventStatus.CANCELLED}
_ANSWERS = {value: key for key, value in PARTSTAT.items()}


def series_of(event: Event) -> Event:
    return event.parent or event


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
    found: list[EventParticipant] = []
    seen: set[str] = set()
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


def request_ical(series: Event, occurrences: list[Event] | None = None) -> str:
    """REQUEST of the series, or of only the given changed occurrences (for who is invited to those
    alone: they get those occurrences, not the series)."""
    components = build_series_ical(series, audience=SCHEDULING)
    if occurrences is not None:
        wanted = {as_utc(replaced_start(o)) for o in occurrences}
        components = [c for c in components[1:] if _recurrence_id(c) in wanted]
    cal = new_calendar("REQUEST")
    for component in components:
        cal.add_component(component)
    return to_ical(cal)


def _recurrence_id(component: icalendar.Component) -> datetime | None:
    rid = component.get("RECURRENCE-ID")
    if rid is None:
        return None
    value = rid.dt
    return as_utc(value if isinstance(value, datetime) else datetime(value.year, value.month, value.day))


def cancel_ical(
    series: Event, participants: list[EventParticipant], sequence: int, occurrence: Event | None = None
) -> str:
    """CANCEL of the whole event, or of one occurrence (with its RECURRENCE-ID), naming the
    participants it is sent to."""
    if occurrence is None:
        vevent = build_series_ical(series, audience=SCHEDULING)[0]
    else:
        occurrence.parent = series
        vevent = build_event_ical(occurrence, uid=series.uid, audience=SCHEDULING, organizer=series.creator)
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


def _message(
    series: Event,
    participant: EventParticipant,
    method: str,
    ical_text: str,
    kind: str,
    shown: Event | None = None,
) -> EmailMultiAlternatives:
    """`kind`: "invite", "update", "cancel" or "removed". `shown`: the occurrence the mail is about,
    if it is about one only."""
    organizer = series.creator
    shown = shown or series
    language = mail.language_of(participant.user, fallback=mail.language_of(organizer))
    reader = mail.Reader.of(participant.user, language, shown.timezone)
    title = shown.title or series.title or text(language, "untitled")
    when = mail.format_when(shown.start, shown.end, shown.all_day, reader)
    name = organizer.display_name or organizer.email

    subject_kind = "cancel" if kind == "removed" else kind
    paragraphs = [text(language, f"{kind}_body", organizer=name, title=title)]
    details = [(text(language, "when"), when)]
    if shown.location:
        details.append((text(language, "location"), shown.location))
    details.append((text(language, "organizer"), f"{name} <{organizer.email}>"))
    if shown.description and method == "REQUEST":
        details.append((text(language, "description"), shown.description))

    links: list[mail.Link] = []
    if method == "REQUEST":
        paragraphs.append(text(language, "rsvp_prompt"))
        # The answer page shows the whole event, also to guests without an account.
        url = mail.app_link(f"/rsvp/{participant.rsvp_token}")
        if url:
            links.append(mail.Link(text(language, "view_event"), url, primary=True))
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
        heading=title,
    )
    # Inline for mail programs that show invitations, and as file for those that don't.
    message.attach_alternative(ical_text, f"text/calendar; method={method}")
    message.attach("invite.ics", ical_text, f"text/calendar; method={method}")
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
    kind = "update" if update else "invite"
    # Who is invited to the series gets all of it; who is invited to changed occurrences only, those.
    on_series = {p.email.lower() for p in series.participants.all()}
    overrides = [o for o in series.overrides.prefetch_related("participants") if o.status not in _GONE]
    series_text = None
    messages: list[EmailMultiAlternatives] = []
    for participant in recipients:
        address = participant.email.lower()
        if address in on_series:
            series_text = series_text or request_ical(series)
            messages.append(_message(series, participant, "REQUEST", series_text, kind))
            continue
        theirs = [o for o in overrides if any(p.email.lower() == address for p in o.participants.all())]
        if theirs:
            text_ = request_ical(series, theirs)
            messages.append(_message(series, participant, "REQUEST", text_, kind, shown=theirs[0]))
    mail.send(messages)


def send_cancel(event: Event, participants: list[EventParticipant] | None = None) -> None:
    """Tells participants (all, or those given and taken off it) that the event doesn't take place.

    Call it before deleting the event: the message is built from the event as it still is.
    """
    series = series_of(event)
    # A changed occurrence (cancelled, rejected, or someone taken off it): that occurrence only.
    occurrence = event if event.parent_id else None
    recipients = _recipients(series, participants)
    if not recipients:
        return
    bump_sequence(series)
    ical_text = cancel_ical(series, recipients, series.sequence, occurrence)
    kind = "removed" if participants is not None else "cancel"
    mail.send(_message(series, p, "CANCEL", ical_text, kind, shown=occurrence) for p in recipients)


# Answers --------------------------------------------------------------------------------------


def record_answer(participant: EventParticipant, status: str, name: str | None = None) -> bool:
    """A participant's own answer, from the app, the link in the invitation or their mail program.

    An answer for a series holds for its changed occurrences too. Tells the organizer.
    """
    if participant.status == status:
        return False
    previous = participant.status
    participant.status = status
    participant.save()
    event = participant.event
    if not event.parent_id:
        # Occurrences answered the same as the series follow it; one answered on its own keeps that.
        for other in EventParticipant.objects.filter(event__parent=event, email__iexact=participant.email):
            if other.status == previous:
                other.status = status
                other.save()
    series = series_of(event)
    # A change of the event for CalDAV clients (ETag, sync token), so the organizer's sees the answer.
    Event.objects.filter(Q(id=series.id) | Q(parent=series)).update(updated_at=timezone.now())
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


def _address(value: object) -> str:
    return str(value or "").strip().lower().removeprefix("mailto:")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _reply(vevent: icalendar.Component, sender: str | None) -> list[str]:
    uid = str(vevent.get("UID", ""))
    rid = vevent.get("RECURRENCE-ID")
    occurrence = None
    if rid is not None:
        value = rid.dt
        occurrence = as_utc(value if isinstance(value, datetime) else datetime(value.year, value.month, value.day))
    results: list[str] = []
    for attendee in _as_list(vevent.get("ATTENDEE")):
        address = _address(attendee)
        params = getattr(attendee, "params", {})
        status = _ANSWERS.get(str(params.get("PARTSTAT", "")).upper())
        if status is None:
            results.append(f"{uid}: {address}: unsupported answer {params.get('PARTSTAT')!r}")
            continue
        # Only the participant answers for themselves. SENT-BY is written by whoever sends the mail,
        # so it proves nothing; someone answering for them uses the link in the invitation.
        if sender is not None and sender != address:
            results.append(f"{uid}: {address}: ignored, sent by {sender}")
            continue
        participants = EventParticipant.objects.select_related("event", "event__parent", "user").filter(
            event__uid=uid, email__iexact=address
        )
        found = list(
            participants.filter(event__parent__isnull=True)
            if occurrence is None
            else participants.filter(event__recurrence_id=occurrence)
        )
        if not found and occurrence is not None:
            # An answer for one occurrence that hasn't been changed yet (mail programs send these
            # when someone accepts or declines one meeting of a series): it becomes a changed one.
            found = _occurrence_participants(participants.filter(event__parent__isnull=True), occurrence)
        if not found:
            results.append(f"{uid}: {address}: no such invitation")
            continue
        series = series_of(found[0].event)
        if series.status in _GONE or any(p.event.status in _GONE for p in found):
            results.append(f"{uid}: {address}: ignored, the event was cancelled")
            continue
        for participant in found:
            changed = record_answer(participant, status, params.get("CN"))
            results.append(f"{uid}: {address}: {status}" + ("" if changed else " (unchanged)"))
    return results


def _occurrence_participants(
    series_participants: QuerySet[EventParticipant], occurrence: datetime
) -> list[EventParticipant]:
    found: list[EventParticipant] = []
    for participant in series_participants:
        series = participant.event
        if not is_series(series) or not is_occurrence(series, occurrence):
            continue
        override = override_for(series, occurrence)
        found += list(override.participants.select_related("event", "user").filter(email__iexact=participant.email))
    return found


def _refresh(vevent: icalendar.Component, sender: str | None) -> list[str]:
    """A participant asks for the event again."""
    uid = str(vevent.get("UID", ""))
    results: list[str] = []
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
    handlers: dict[str, Callable[[icalendar.Component, str | None], list[str]]] = {"REPLY": _reply, "REFRESH": _refresh}
    handler = handlers.get(method)
    if handler is None:
        return [f"method {method or 'none'} ignored"]
    results: list[str] = []
    for vevent in cal.walk("VEVENT"):
        results += handler(vevent, sender)
    return results


def sender_verified(message: Message, sender: str) -> bool:
    """Whether the receiving mail server (IMIP_TRUSTED_AUTHSERV_ID) verified the sender's domain:
    DMARC passed for it, or a DKIM signature of it did. Its Authentication-Results header is the one
    it added; others with another server's name may come from anyone."""
    domain = sender.rpartition("@")[2]
    if not domain:
        return False
    for header in message.get_all("Authentication-Results") or []:
        authserv_id, _, results = str(header).partition(";")
        if authserv_id.strip().split()[0].lower() != settings.IMIP_TRUSTED_AUTHSERV_ID:
            continue
        for result in results.split(";"):
            words = result.lower().split()
            if not words:
                continue
            props = dict(word.partition("=")[::2] for word in words[1:])
            if words[0] == "dmarc=pass" and props.get("header.from") == domain:
                return True
            if words[0] == "dkim=pass" and props.get("header.d") == domain:
                return True
    return False


def process_email(raw: bytes, trust_sender: bool = False) -> list[str]:
    """Applies the iTIP messages in an email; answers count only for the address that sent them."""
    message = email.message_from_bytes(raw, policy=email.policy.default)
    senders = getaddresses([str(message.get("From", ""))])
    sender = None if trust_sender else (senders[0][1].lower() if senders and senders[0][1] else "")
    if sender and settings.IMIP_TRUSTED_AUTHSERV_ID and not sender_verified(message, sender):
        return [f"ignored: the sender {sender} wasn't verified by {settings.IMIP_TRUSTED_AUTHSERV_ID}"]
    seen: set[bytes] = set()
    results: list[str] = []
    for part in message.walk():
        filename = (part.get_filename() or "").lower()
        if part.get_content_type() not in ("text/calendar", "application/ics") and not filename.endswith(".ics"):
            continue
        payload = part.get_payload(decode=True)
        # The same message often comes inline and as attachment; decoded, a part is bytes (None if multipart).
        if not isinstance(payload, bytes) or not payload or payload in seen:
            continue
        seen.add(payload)
        results += process_itip(payload, sender)
    return results or ["no iTIP message found"]


IMAP_TIMEOUT = 30  # seconds


def fetch_mailbox() -> list[str]:
    """Applies the unread messages in the iMIP mailbox (IMAP) and marks them read."""
    if not settings.IMIP_IMAP_HOST:
        raise RuntimeError("IMIP_IMAP_HOST is not set")
    connect = imaplib.IMAP4_SSL if settings.IMIP_IMAP_SSL else imaplib.IMAP4
    results: list[str] = []
    # With a timeout: a server that stops answering would hold up the worker, and every job with it.
    with connect(settings.IMIP_IMAP_HOST, settings.IMIP_IMAP_PORT, timeout=IMAP_TIMEOUT) as imap:
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
