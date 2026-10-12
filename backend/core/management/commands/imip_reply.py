"""
Development: answers an invitation as a participant's mail program would, with an iTIP REPLY
email to the event's organizer address. Sent through the configured mail server (e.g. Mailpit),
from where `fetch_imip` picks it up; or applied right away with `--process`.
"""

from datetime import datetime, timezone

import icalendar
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError

from core.models import EventParticipant
from core.services.ical import PARTSTAT, new_calendar, organizer_address, to_ical
from core.services.itip import process_email, series_of


def reply_email(participant: EventParticipant, status: str) -> EmailMessage:
    series = series_of(participant.event)
    vevent = icalendar.Event()
    vevent.add("uid", series.uid)
    vevent.add("dtstamp", datetime.now(timezone.utc))
    vevent.add("sequence", series.sequence)
    vevent.add("summary", series.title)
    vevent.add("dtstart", series.start)
    organizer = organizer_address(series.creator, scheduling=True)
    vevent.add("organizer", icalendar.vCalAddress(f"mailto:{organizer}"))
    vevent.add(
        "attendee",
        icalendar.vCalAddress(f"mailto:{participant.email}"),
        parameters={"PARTSTAT": PARTSTAT[status]},
    )
    cal = new_calendar("REPLY")
    cal.add_component(vevent)
    ical_text = to_ical(cal)

    message = EmailMessage(
        subject=f"{status.replace('_', ' ').title()}: {series.title}",
        body=f"{participant.email} answered: {status}\n",
        from_email=participant.email,
        to=[organizer],
    )
    message.attach("reply.ics", ical_text, "text/calendar; method=REPLY")
    return message


class Command(BaseCommand):
    help = "Development: sends an iTIP REPLY for a participant of an event, as their mail program would."

    def add_arguments(self, parser):
        parser.add_argument("event_id")
        parser.add_argument("email", help="The participant's address.")
        parser.add_argument("status", choices=["accepted", "tentative", "declined"])
        parser.add_argument("--process", action="store_true", help="Apply it right away instead of sending it.")

    def handle(self, *args, event_id, email, status, process, **options):
        participant = (
            EventParticipant.objects.select_related("event").filter(event_id=event_id, email__iexact=email).first()
        )
        if participant is None:
            raise CommandError(f"{email} is not a participant of event {event_id}")
        message = reply_email(participant, status)
        if process:
            for line in process_email(message.message().as_bytes()):
                self.stdout.write(line)
            return
        message.send()
        self.stdout.write(f"REPLY sent to {message.to[0]}; apply it with: manage.py fetch_imip")
