"""
An event's location: free text, or a place (a resource marked as location) that it books besides
its resource. Each booking is approved by its own approvers.
"""

from datetime import timedelta

import pytest

from core.models import Event
from core.tests.helpers import BASE, iso

pytestmark = pytest.mark.django_db


def create(world, user="booker", start=BASE, **fields):
    data = {"title": "Meeting", "start": iso(start), "end": iso(start + timedelta(hours=1)), **fields}
    return world["api"][user].post(f"/calendars/{world['cal']['id']}/events", data)


@pytest.fixture
def places(world):
    users = world["users"]
    room = world["resource"]("Room 1", requires_approval=True, is_location=True, approver_ids=[str(users["approver"].id)])
    projector = world["resource"]("Projector", requires_approval=True, approver_ids=[str(users["resapprover"].id)])
    hall = world["resource"]("Hall", requires_approval=False, is_location=True)
    return {"room": room, "projector": projector, "hall": hall}


def test_free_text_location(world):
    event = create(world, location="Café Central").json()
    assert (event["location"], event["location_resource_id"]) == ("Café Central", None)
    assert event["status"] == "confirmed"


def test_places_and_resources_go_in_their_own_field(world, places):
    assert create(world, resource_id=places["hall"]["id"]).status_code == 404
    assert create(world, location_resource_id=places["projector"]["id"]).status_code == 404
    found = world["api"]["booker"].get(f"/search?entity=locations&calendar_id={world['cal']['id']}").json()
    assert sorted(r["label"] for r in found) == ["Hall", "Room 1"]
    found = world["api"]["booker"].get(f"/search?entity=resources&calendar_id={world['cal']['id']}").json()
    assert [r["label"] for r in found] == ["Projector"]


def test_a_place_is_booked_once_at_a_time(world, places):
    first = create(world, location_resource_id=places["hall"]["id"], location="ignored").json()
    assert (first["location"], first["location_resource_name"], first["status"]) == ("Hall", "Hall", "confirmed")
    clash = create(world, "other", start=BASE + timedelta(minutes=30), location_resource_id=places["hall"]["id"])
    assert clash.status_code == 409
    # Without the place, the same time is fine.
    assert create(world, "other", start=BASE + timedelta(minutes=30), location="Hall foyer").status_code == 200


def test_each_booking_is_approved_by_its_approvers(world, places):
    users, api = world["users"], world["api"]
    event = create(world, location_resource_id=places["room"]["id"], resource_id=places["projector"]["id"]).json()
    assert event["status"] == "pending"
    assert sorted(event["awaiting_approval"]) == ["Projector", "Room 1"]

    # Each approver sees the request and decides on their own booking only.
    assert [a["id"] for a in api["approver"].get("/approvals").json()] == [event["id"]]
    res = api["approver"].post(f"/events/{event['id']}/approve", {})
    assert res.status_code == 200
    assert (res.json()["status"], res.json()["awaiting_approval"]) == ("pending", ["Projector"])
    assert api["approver"].get("/approvals").json() == []
    assert api["approver"].post(f"/events/{event['id']}/approve", {}).status_code == 403

    res = api["resapprover"].post(f"/events/{event['id']}/approve", {})
    assert (res.json()["status"], res.json()["awaiting_approval"]) == ("approved", [])
    assert Event.objects.get(id=event["id"]).decided_by == users["resapprover"]


def test_one_rejection_rejects_the_event(world, places):
    event = create(world, location_resource_id=places["room"]["id"], resource_id=places["projector"]["id"]).json()
    res = world["api"]["resapprover"].post(f"/events/{event['id']}/reject", {"note": "Broken"})
    assert res.json()["status"] == "rejected"


def test_changing_one_booking_keeps_the_others_approval(world, places):
    api = world["api"]
    event = create(world, location_resource_id=places["room"]["id"]).json()
    api["approver"].post(f"/events/{event['id']}/approve", {})
    res = api["booker"].patch(f"/events/{event['id']}", {"resource_id": places["projector"]["id"]})
    assert (res.json()["status"], res.json()["awaiting_approval"]) == ("pending", ["Projector"])
    # Moving the event needs both approvals again.
    api["resapprover"].post(f"/events/{event['id']}/approve", {})
    later = BASE + timedelta(days=1)
    res = api["booker"].patch(f"/events/{event['id']}", {"start": iso(later), "end": iso(later + timedelta(hours=1))})
    assert sorted(res.json()["awaiting_approval"]) == ["Projector", "Room 1"]


def test_typing_another_location_gives_the_place_up(world, places):
    event = create(world, location_resource_id=places["hall"]["id"]).json()
    res = world["api"]["booker"].patch(f"/events/{event['id']}", {"location": "Online"})
    assert (res.json()["location"], res.json()["location_resource_id"]) == ("Online", None)


def test_availability_includes_bookings_of_places(world, places):
    create(world, location_resource_id=places["hall"]["id"])
    data = {"start": iso(BASE - timedelta(hours=1)), "end": iso(BASE + timedelta(hours=5)), "resource_ids": [places["hall"]["id"]]}
    body = world["api"]["owner"].post("/availability", data).json()
    assert [(p["start"][11:16], p["tentative"]) for p in body["resources"][0]["busy"]] == [("09:00", False)]
