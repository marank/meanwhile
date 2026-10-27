"""
Answering an invitation from the link in its email: the token in the link is the participant's
key, so no account or session is needed. Signed in as the participant, the page leads into the app.
"""

from uuid import UUID

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from ninja import Router
from ninja.errors import HttpError

from core.models import EventParticipant, User
from core.models.base import EventStatus, ParticipantStatus
from core.schemas import RsvpAnswer, RsvpOut, RsvpParticipantOut
from core.services.ical import FEED, build_event_ical, build_series_ical, new_calendar, to_ical
from core.services.itip import record_answer, series_of
from core.services.permissions import get_visible_event
from core.services.recurrence import as_utc

router = Router()

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


def _name(participant: EventParticipant) -> str:
    return participant.user.display_name if participant.user else ""


def _owner(participant: EventParticipant, request: HttpRequest) -> User | None:
    """The signed-in user, if the invitation is theirs (by account or by address)."""
    user = request.user
    if not isinstance(user, User):
        return None
    if participant.user_id == user.id or participant.email.lower() == user.email.lower():
        return user
    return None


def _event_in_app(participant: EventParticipant, user: User | None) -> UUID | None:
    """The event, if its participant can open it in the app (not everyone invited can see the calendar)."""
    if user is None:
        return None
    try:
        get_visible_event(str(participant.event_id), user)
    except HttpError:
        return None
    return participant.event_id


def _serialize(participant: EventParticipant, request: HttpRequest) -> RsvpOut:
    event = participant.event
    user = _owner(participant, request)
    series = series_of(event)
    organizer = series.creator
    return RsvpOut(
        title=event.title,
        start=as_utc(event.start),
        end=as_utc(event.end),
        all_day=event.all_day,
        timezone=event.timezone,
        location=event.location,
        description=event.description,
        rrule=series.rrule,
        organizer_name=organizer.display_name,
        email=participant.email,
        status=ParticipantStatus(participant.status),
        cancelled=event.status in _GONE,
        participants=[
            RsvpParticipantOut(
                name=_name(other) or (other.email if other.id == participant.id else None),
                status=ParticipantStatus(other.status),
                you=other.id == participant.id,
            )
            for other in event.participants.select_related("user").order_by("email")
        ],
        yours=user is not None,
        event_id=_event_in_app(participant, user),
    )


@router.get("/rsvp/{token}", response=RsvpOut, auth=None)
def get_invitation(request: HttpRequest, token: str) -> RsvpOut:
    return _serialize(_participant(token), request)


@router.post("/rsvp/{token}", response=RsvpOut, auth=None)
def answer_invitation(request: HttpRequest, token: str, payload: RsvpAnswer) -> RsvpOut:
    participant = _participant(token)
    if participant.event.status in _GONE:
        raise HttpError(409, "This event has been cancelled")
    with transaction.atomic():
        record_answer(participant, payload.status)
    return _serialize(participant, request)


@router.get("/rsvp/{token}/ics", auth=None)
def invitation_ics(request: HttpRequest, token: str) -> HttpResponse:
    """The event as a file for calendar apps, without organizer and participants: anyone with the link may
    load it, and answers are given on the page."""
    participant = _participant(token)
    event = participant.event
    series = series_of(event)
    cal = new_calendar("PUBLISH")
    if event.parent_id:
        # Invited to a changed occurrence only: that one.
        event.parent = series
        components = [build_event_ical(event, uid=series.uid, audience=FEED)]
    else:
        components = build_series_ical(series, audience=FEED)
    for component in components:
        cal.add_component(component)
    ical_text = to_ical(cal)
    response = HttpResponse(ical_text, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="invite.ics"'
    return response
