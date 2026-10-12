"""
Answering an invitation from the link in its email: the token in the link is the participant's
key, so no account or session is needed.
"""

from django.db import transaction
from ninja.errors import HttpError

from core.api import CSRFRouter
from core.models import EventParticipant
from core.models.base import EventStatus
from core.schemas import RsvpAnswer, RsvpOut
from core.services.itip import record_answer, series_of
from core.services.recurrence import make_aware

router = CSRFRouter()

_GONE = {EventStatus.REJECTED, EventStatus.CANCELLED}


def _participant(token: str) -> EventParticipant:
    participant = (
        EventParticipant.objects.select_related("event__creator", "event__parent", "user")
        .filter(rsvp_token=token)
        .first()
    )
    if participant is None:
        raise HttpError(404, "This invitation no longer exists")
    return participant


def _serialize(participant: EventParticipant) -> RsvpOut:
    event = participant.event
    series = series_of(event)
    organizer = series.creator
    return RsvpOut(
        title=event.title,
        start=make_aware(event.start),
        end=make_aware(event.end),
        all_day=event.all_day,
        timezone=event.timezone,
        location=event.location,
        description=event.description,
        rrule=series.rrule,
        organizer_name=organizer.display_name or organizer.email,
        email=participant.email,
        status=participant.status,
        cancelled=event.status in _GONE,
    )


@router.get("/rsvp/{token}", response=RsvpOut)
def get_invitation(request, token: str):
    return _serialize(_participant(token))


@router.post("/rsvp/{token}", response=RsvpOut)
def answer_invitation(request, token: str, payload: RsvpAnswer):
    participant = _participant(token)
    if participant.event.status in _GONE:
        raise HttpError(409, "This event has been cancelled")
    with transaction.atomic():
        record_answer(participant, payload.status)
    return _serialize(participant)
