"""
Where notifications lead, in the app and in their emails: one rule for both.
"""

from typing import Any

import pytest
from django.core import mail as django_mail

from apps.core.models import EventParticipant, User
from apps.core.tests.helpers import World, add_default_approver

pytestmark = pytest.mark.django_db


def links(world: World, name: str) -> dict[str, str]:
    """The user's notifications by type, with where each leads."""
    return {n["type"]: n["link"] for n in world["api"][name].get("/notifications").json()}


def booking(world: World) -> dict[str, Any]:
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    event: dict[str, Any] = world["book"](world["api"]["booker"], room["id"]).json()
    return event


def test_notifications_lead_to_their_event_or_calendar(world: World) -> None:
    event = booking(world)
    assert links(world, "approver")["approval_requested"] == f"/event/{event['id']}"
    # Added to the calendar when the world was set up.
    assert links(world, "approver")["member_added"] == f"/calendar/{world['cal']['id']}"


def test_events_one_cannot_see_any_more_lead_to_the_notifications(world: World) -> None:
    event = booking(world)
    django_mail.outbox.clear()
    assert world["api"]["booker"].post(f"/events/{event['id']}/cancel").status_code == 200
    # Cancelled bookings stay visible to full members only.
    assert links(world, "owner")["booking_cancelled"] == f"/event/{event['id']}"
    assert links(world, "approver")["booking_cancelled"] == "/notifications"
    # The email says the same.
    [message] = [m for m in django_mail.outbox if m.to == ["approver@example.test"]]
    assert "/notifications" in message.body
    assert f"/event/{event['id']}" not in message.body


def test_invitations_to_events_out_of_sight_lead_to_the_invitation_page(world: World) -> None:
    owner = world["api"]["owner"]
    event = owner.post(
        f"/calendars/{world['cal']['id']}/events",
        {"title": "Board", "start": "2030-01-07T09:00:00Z", "end": "2030-01-07T10:00:00Z", "timezone": "UTC"},
    ).json()
    outsider: User = world["users"]["outsider"]
    owner.post(f"/events/{event['id']}/participants", {"email": outsider.email})
    token = EventParticipant.objects.get(event_id=event["id"], email=outsider.email).rsvp_token
    assert links(world, "outsider")["participant_added"] == f"/invitation/{token}"
    # A member invited sees the event itself.
    owner.post(f"/events/{event['id']}/participants", {"email": world["users"]["other"].email})
    assert links(world, "other")["participant_added"] == f"/event/{event['id']}"
