"""
Participants of an event, changed in the app: inviting, answering for them and taking them off,
each with the iTIP message that tells them.
"""

from django.db import transaction

from apps.core.models import Event, EventParticipant, User
from apps.core.schemas import EventParticipantCreate
from apps.core.services.events import add_participant
from apps.core.services.itip import record_answer, send_cancel, send_request


@transaction.atomic
def invite(event: Event, actor: User, data: EventParticipantCreate) -> EventParticipant:
    participant = add_participant(event, actor, data)
    send_request(event, [participant])
    return participant


@transaction.atomic
def set_status(participant: EventParticipant, actor: User, status: str) -> None:
    """The participant's own answer goes out to the organizer; one set by someone else is only noted."""
    if participant.user_id == actor.id:
        record_answer(participant, status)
    else:
        participant.status = status
        participant.save()


@transaction.atomic
def remove(event: Event, participant: EventParticipant, actor: User) -> None:
    # Taken off by someone else: told so, for the event or (a changed occurrence) that occurrence only.
    if participant.user_id != actor.id:
        send_cancel(event, [participant])
    participant.delete()
