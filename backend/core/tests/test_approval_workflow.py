"""
End-to-end tests for the resource booking approval workflow, driven through the HTTP API.
"""

import json
from urllib.parse import quote
from datetime import datetime, timedelta, timezone

import pytest
from django.test import Client

from core.models import Event, Notification, User

pytestmark = pytest.mark.django_db

BASE = datetime(2030, 1, 7, 9, 0, tzinfo=timezone.utc)  # a Monday


def iso(dt: datetime) -> str:
    return dt.isoformat()


class Api:
    """Session-authenticated JSON client for one user."""

    def __init__(self, user: User):
        self.client = Client()
        self.client.force_login(user)
        self.user = user

    def _call(self, method: str, url: str, data=None):
        kwargs = {"content_type": "application/json"}
        if data is not None:
            kwargs["data"] = json.dumps(data)
        return getattr(self.client, method)(f"/api{url}", **kwargs)

    def get(self, url):
        return self._call("get", url)

    def post(self, url, data=None):
        return self._call("post", url, data if data is not None else {})

    def patch(self, url, data):
        return self._call("patch", url, data)

    def delete(self, url):
        return self._call("delete", url)


def make_user(name: str) -> User:
    return User.objects.create_user(email=f"{name}@example.test", password="x", display_name=name.title())


@pytest.fixture
def world():
    """A calendar with members in every role relevant to approvals."""
    users = {name: make_user(name) for name in (
        "owner", "editor", "booker", "other", "approver", "resapprover", "outsider",
    )}
    apis = {name: Api(user) for name, user in users.items()}
    owner = apis["owner"]

    cal = owner.post("/calendars", {"name": "Team"}).json()
    for name, role in (
        ("editor", "editor"),
        ("booker", "contributor"),
        ("other", "contributor"),
        ("approver", "contributor"),
        ("resapprover", "contributor"),
    ):
        res = owner.post(f"/calendars/{cal['id']}/members", {"user_id": str(users[name].id), "role": role})
        assert res.status_code == 200, res.content

    def resource(name: str, requires_approval: bool = True, **extra):
        res = owner.post(
            f"/calendars/{cal['id']}/resources",
            {"name": name, "requires_approval": requires_approval, **extra},
        )
        assert res.status_code == 200, res.content
        return res.json()

    def book(api: Api, resource_id: str | None, start: datetime = BASE, hours: int = 1, **extra):
        return api.post(f"/calendars/{cal['id']}/events", {
            "title": extra.pop("title", "Booking"),
            "start": iso(start),
            "end": iso(start + timedelta(hours=hours)),
            "resource_id": resource_id,
            **extra,
        })

    return {"users": users, "api": apis, "cal": cal, "resource": resource, "book": book}


def notified(user: User, type_: str, event_id: str) -> bool:
    return Notification.objects.filter(user=user, type=type_, event_id=event_id).exists()


def add_default_approver(world, name: str):
    res = world["api"]["owner"].post(
        f"/calendars/{world['cal']['id']}/approvers", {"user_id": str(world["users"][name].id)}
    )
    assert res.status_code == 200, res.content


def add_resource_approver(world, resource_id: str, name: str):
    return world["api"]["owner"].post(
        f"/calendars/{world['cal']['id']}/resources/{resource_id}/approvers",
        {"user_id": str(world["users"][name].id)},
    )


# --- Booking without and with approval ---------------------------------------------------


def test_resource_without_approval_is_confirmed_immediately(world):
    beamer = world["resource"]("Beamer", requires_approval=False)
    res = world["book"](world["api"]["booker"], beamer["id"])
    assert res.status_code == 200, res.content
    event = res.json()
    assert event["status"] == "confirmed"
    assert not Notification.objects.filter(type="approval_requested").exists()


def test_booking_without_resource_is_confirmed(world):
    res = world["book"](world["api"]["booker"], None)
    assert res.json()["status"] == "confirmed"


def test_booking_requiring_approval_is_pending_and_notifies_pool(world):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    event = world["book"](world["api"]["booker"], room["id"]).json()
    u = world["users"]
    assert event["status"] == "pending"
    assert notified(u["approver"], "approval_requested", event["id"])
    assert notified(u["owner"], "approval_requested", event["id"])
    assert not notified(u["booker"], "approval_requested", event["id"])
    assert not notified(u["other"], "approval_requested", event["id"])


def test_pending_list_shows_requests_only_to_the_pool(world):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    event = world["book"](world["api"]["booker"], room["id"]).json()
    api = world["api"]

    def pending_ids(name):
        return [e["id"] for e in api[name].get("/approvals").json()]

    assert event["id"] in pending_ids("approver")
    assert event["id"] in pending_ids("owner")
    assert event["id"] not in pending_ids("other")
    assert event["id"] not in pending_ids("booker")
    pool = api["approver"].get("/approvals").json()[0]["approver_pool"]
    assert [p["user_id"] for p in pool] == [str(world["users"]["approver"].id)]


# --- Decisions ---------------------------------------------------------------------------


def test_default_approver_approves(world):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    event = world["book"](world["api"]["booker"], room["id"]).json()

    res = world["api"]["approver"].post(f"/events/{event['id']}/approve", {"note": "ok"})
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["status"] == "approved"
    assert body["decided_by"] == str(world["users"]["approver"].id)
    assert body["decision_note"] == "ok"
    assert notified(world["users"]["booker"], "booking_approved", event["id"])
    assert event["id"] not in [e["id"] for e in world["api"]["approver"].get("/approvals").json()]

    again = world["api"]["approver"].post(f"/events/{event['id']}/approve")
    assert again.status_code == 400


def test_default_approver_rejects_with_note(world):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    event = world["book"](world["api"]["booker"], room["id"]).json()

    res = world["api"]["approver"].post(f"/events/{event['id']}/reject", {"note": "booked out"})
    assert res.status_code == 200, res.content
    assert res.json()["status"] == "rejected"
    assert res.json()["decision_note"] == "booked out"
    assert notified(world["users"]["booker"], "booking_rejected", event["id"])
    assert world["api"]["approver"].post(f"/events/{event['id']}/approve").status_code == 400


@pytest.mark.parametrize("name", ["other", "booker", "editor"])
def test_members_outside_the_pool_cannot_decide(world, name):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    event = world["book"](world["api"]["booker"], room["id"]).json()
    api = world["api"][name]
    assert api.post(f"/events/{event['id']}/approve").status_code == 403
    assert api.post(f"/events/{event['id']}/reject").status_code == 403
    assert Event.objects.get(id=event["id"]).status == "pending"


def test_outsider_cannot_decide(world):
    room = world["resource"]("Room")
    event = world["book"](world["api"]["booker"], room["id"]).json()
    assert world["api"]["outsider"].post(f"/events/{event['id']}/approve").status_code == 403


def test_resource_approvers_take_precedence_over_defaults(world):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    assert add_resource_approver(world, room["id"], "resapprover").status_code == 200
    event = world["book"](world["api"]["booker"], room["id"]).json()
    u = world["users"]

    assert notified(u["resapprover"], "approval_requested", event["id"])
    assert not notified(u["approver"], "approval_requested", event["id"])
    assert world["api"]["approver"].post(f"/events/{event['id']}/approve").status_code == 403
    assert world["api"]["resapprover"].post(f"/events/{event['id']}/approve").status_code == 200


def test_without_any_approvers_only_the_owner_decides(world):
    room = world["resource"]("Room")
    event = world["book"](world["api"]["booker"], room["id"]).json()
    assert event["status"] == "pending"
    assert notified(world["users"]["owner"], "approval_requested", event["id"])
    approvals = world["api"]["owner"].get("/approvals").json()
    assert approvals[0]["approver_pool"] == []
    assert world["api"]["owner"].post(f"/events/{event['id']}/approve").status_code == 200


def test_owner_can_always_decide(world):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    assert add_resource_approver(world, room["id"], "resapprover").status_code == 200
    event = world["book"](world["api"]["booker"], room["id"]).json()
    assert world["api"]["owner"].post(f"/events/{event['id']}/reject").status_code == 200


def test_resource_approver_must_be_calendar_member(world):
    room = world["resource"]("Room")
    res = add_resource_approver(world, room["id"], "outsider")
    assert res.status_code == 400


# --- Conflicts ---------------------------------------------------------------------------


def test_booking_over_an_approved_slot_is_refused(world):
    room = world["resource"]("Room")
    first = world["book"](world["api"]["booker"], room["id"]).json()
    world["api"]["owner"].post(f"/events/{first['id']}/approve")

    res = world["book"](world["api"]["other"], room["id"], start=BASE + timedelta(minutes=30))
    assert res.status_code == 409
    assert not Event.objects.filter(creator=world["users"]["other"]).exists()


def test_overlapping_pending_requests_conflict_on_approval(world):
    room = world["resource"]("Room")
    a = world["book"](world["api"]["booker"], room["id"]).json()
    b = world["book"](world["api"]["other"], room["id"], start=BASE + timedelta(minutes=30))
    assert b.status_code == 200
    b = b.json()

    assert world["api"]["owner"].post(f"/events/{a['id']}/approve").status_code == 200
    res = world["api"]["owner"].post(f"/events/{b['id']}/approve")
    assert res.status_code == 409
    assert Event.objects.get(id=b["id"]).status == "pending"
    assert world["api"]["owner"].post(f"/events/{b['id']}/reject").status_code == 200


def test_adjacent_bookings_do_not_conflict(world):
    room = world["resource"]("Room")
    a = world["book"](world["api"]["booker"], room["id"]).json()
    world["api"]["owner"].post(f"/events/{a['id']}/approve")
    res = world["book"](world["api"]["other"], room["id"], start=BASE + timedelta(hours=1))
    assert res.status_code == 200


def test_rejected_and_cancelled_bookings_free_the_slot(world):
    room = world["resource"]("Room")
    a = world["book"](world["api"]["booker"], room["id"]).json()
    world["api"]["owner"].post(f"/events/{a['id']}/approve")
    world["api"]["booker"].post(f"/events/{a['id']}/cancel")
    b = world["book"](world["api"]["other"], room["id"])
    assert b.status_code == 200
    assert world["api"]["owner"].post(f"/events/{b.json()['id']}/approve").status_code == 200


def test_recurring_approved_booking_blocks_later_occurrences(world):
    room = world["resource"]("Room")
    weekly = world["book"](world["api"]["booker"], room["id"], rrule="FREQ=WEEKLY;COUNT=4").json()
    assert world["api"]["owner"].post(f"/events/{weekly['id']}/approve").status_code == 200

    third_week = world["book"](world["api"]["other"], room["id"], start=BASE + timedelta(weeks=2))
    assert third_week.status_code == 409
    after_series = world["book"](world["api"]["other"], room["id"], start=BASE + timedelta(weeks=4))
    assert after_series.status_code == 200


def test_bookings_on_other_resources_do_not_conflict(world):
    room = world["resource"]("Room")
    hall = world["resource"]("Hall")
    a = world["book"](world["api"]["booker"], room["id"]).json()
    world["api"]["owner"].post(f"/events/{a['id']}/approve")
    assert world["book"](world["api"]["other"], hall["id"]).status_code == 200


# --- Editing a booking -------------------------------------------------------------------


def approved_booking(world):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    event = world["book"](world["api"]["booker"], room["id"]).json()
    world["api"]["approver"].post(f"/events/{event['id']}/approve")
    return room, event


def test_rescheduling_an_approved_booking_needs_approval_again(world):
    _, event = approved_booking(world)
    res = world["api"]["booker"].patch(f"/events/{event['id']}", {
        "start": iso(BASE + timedelta(days=1)),
        "end": iso(BASE + timedelta(days=1, hours=1)),
    })
    assert res.status_code == 200, res.content
    assert res.json()["status"] == "pending"
    assert res.json()["decided_by"] is None
    assert Notification.objects.filter(
        user=world["users"]["approver"], type="approval_requested", event_id=event["id"]
    ).count() == 2


def test_renaming_an_approved_booking_keeps_the_approval(world):
    _, event = approved_booking(world)
    res = world["api"]["booker"].patch(f"/events/{event['id']}", {"title": "Renamed"})
    assert res.json()["status"] == "approved"


def test_saving_the_edit_form_unchanged_keeps_the_approval(world):
    """The event dialog always sends every field, even the ones that did not change."""
    room, event = approved_booking(world)
    res = world["api"]["booker"].patch(f"/events/{event['id']}", {
        "title": "Renamed",
        "start": event["start"],
        "end": event["end"],
        "all_day": False,
        "show_recurrence_count": False,
        "rrule": None,
        "category_id": None,
        "resource_id": room["id"],
    })
    assert res.status_code == 200, res.content
    assert res.json()["status"] == "approved"


def test_switching_to_a_resource_without_approval_confirms(world):
    _, event = approved_booking(world)
    beamer = world["resource"]("Beamer", requires_approval=False)
    res = world["api"]["booker"].patch(f"/events/{event['id']}", {"resource_id": beamer["id"]})
    assert res.json()["status"] == "confirmed"


def test_switching_to_another_approval_resource_is_pending(world):
    _, event = approved_booking(world)
    hall = world["resource"]("Hall")
    res = world["api"]["booker"].patch(f"/events/{event['id']}", {"resource_id": hall["id"]})
    assert res.json()["status"] == "pending"


def test_removing_the_resource_confirms_the_event(world):
    _, event = approved_booking(world)
    res = world["api"]["booker"].patch(f"/events/{event['id']}", {"resource_id": None})
    assert res.json()["status"] == "confirmed"
    assert res.json()["resource_id"] is None


def test_rescheduling_into_an_approved_slot_is_refused(world):
    room, event = approved_booking(world)
    later = world["book"](world["api"]["other"], room["id"], start=BASE + timedelta(hours=3)).json()
    res = world["api"]["other"].patch(f"/events/{later['id']}", {
        "start": event["start"],
        "end": event["end"],
    })
    assert res.status_code == 409
    assert Event.objects.get(id=later["id"]).start == BASE + timedelta(hours=3)


def test_other_contributors_cannot_edit_a_booking(world):
    _, event = approved_booking(world)
    res = world["api"]["other"].patch(f"/events/{event['id']}", {"title": "Mine now"})
    assert res.status_code == 403


# --- Cancelling --------------------------------------------------------------------------


def test_creator_cancels_and_pool_is_notified(world):
    _, event = approved_booking(world)
    res = world["api"]["booker"].post(f"/events/{event['id']}/cancel")
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"
    assert notified(world["users"]["approver"], "booking_cancelled", event["id"])
    assert notified(world["users"]["owner"], "booking_cancelled", event["id"])
    assert world["api"]["owner"].post(f"/events/{event['id']}/approve").status_code == 400


def test_editor_can_cancel_but_other_contributor_cannot(world):
    _, event = approved_booking(world)
    assert world["api"]["other"].post(f"/events/{event['id']}/cancel").status_code == 403
    assert world["api"]["editor"].post(f"/events/{event['id']}/cancel").status_code == 200


def test_pending_request_can_be_withdrawn(world):
    room = world["resource"]("Room")
    event = world["book"](world["api"]["booker"], room["id"]).json()
    assert world["api"]["booker"].post(f"/events/{event['id']}/cancel").status_code == 200
    assert world["api"]["owner"].get("/approvals").json() == []


# --- Inactive and archived resources -----------------------------------------------------


def test_inactive_resource_cannot_be_booked(world):
    room = world["resource"]("Room")
    world["api"]["owner"].patch(f"/calendars/{world['cal']['id']}/resources/{room['id']}", {"is_active": False})
    assert world["book"](world["api"]["booker"], room["id"]).status_code == 404


def test_archived_resource_cannot_be_booked(world):
    room = world["resource"]("Room")
    world["api"]["owner"].delete(f"/calendars/{world['cal']['id']}/resources/{room['id']}")
    assert world["book"](world["api"]["booker"], room["id"]).status_code == 404


def test_pending_request_survives_resource_deactivation(world):
    room = world["resource"]("Room")
    event = world["book"](world["api"]["booker"], room["id"]).json()
    world["api"]["owner"].patch(f"/calendars/{world['cal']['id']}/resources/{room['id']}", {"is_active": False})
    assert world["api"]["owner"].post(f"/events/{event['id']}/approve").status_code == 200


def test_editing_a_booking_on_a_deactivated_resource_keeps_it(world):
    room, event = approved_booking(world)
    world["api"]["owner"].patch(f"/calendars/{world['cal']['id']}/resources/{room['id']}", {"is_active": False})
    res = world["api"]["booker"].patch(f"/events/{event['id']}", {"title": "Renamed"})
    assert res.status_code == 200
    assert res.json()["resource_id"] == room["id"]


# --- Response shapes, member search and group access -------------------------------------


def test_conflict_response_names_the_conflicting_booking(world):
    room = world["resource"]("Room")
    first = world["book"](world["api"]["booker"], room["id"]).json()
    world["api"]["owner"].post(f"/events/{first['id']}/approve")
    res = world["book"](world["api"]["other"], room["id"])
    assert res.status_code == 409
    detail = res.json()["detail"]
    assert detail["message"]
    assert detail["conflicts"] == [first["id"]]


def test_approver_search_only_offers_calendar_members(world):
    res = world["api"]["owner"].get(f"/search?entity=members&q=&calendar_id={world['cal']['id']}")
    assert res.status_code == 200
    names = {r["label"] for r in res.json()}
    assert "Approver" in names and "Owner" in names
    assert "Outsider" not in names
    assert world["api"]["outsider"].get(
        f"/search?entity=members&q=&calendar_id={world['cal']['id']}"
    ).status_code == 403


def test_group_members_can_request_bookings(world):
    from core.models import CalendarGroup, UserGroup

    group = UserGroup.objects.create(name="Crew")
    world["users"]["outsider"].groups.add(group)
    CalendarGroup.objects.create(calendar_id=world["cal"]["id"], group=group, role="contributor")

    room = world["resource"]("Room")
    res = world["book"](world["api"]["outsider"], room["id"])
    assert res.status_code == 200, res.content
    assert res.json()["status"] == "pending"


# --- Viewing bookings --------------------------------------------------------------------


def test_bookings_can_be_opened(world):
    room = world["resource"]("Room")
    event = world["book"](world["api"]["booker"], room["id"]).json()
    for name in ("booker", "owner"):
        res = world["api"][name].get(f"/events/{event['id']}")
        assert res.status_code == 200, (name, res.content)
        assert res.json()["status"] == "pending"
    assert world["api"]["booker"].get(f"/events/{event['id']}/comments").status_code == 200


def test_rejected_booking_is_hidden_from_other_contributors(world):
    room = world["resource"]("Room")
    event = world["book"](world["api"]["booker"], room["id"]).json()
    world["api"]["owner"].post(f"/events/{event['id']}/reject")
    assert world["api"]["booker"].get(f"/events/{event['id']}").status_code == 200
    assert world["api"]["editor"].get(f"/events/{event['id']}").status_code == 200
    assert world["api"]["other"].get(f"/events/{event['id']}").status_code == 404
    assert world["api"]["outsider"].get(f"/events/{event['id']}").status_code == 404


def test_unknown_event_is_not_found(world):
    assert world["api"]["owner"].get("/events/does-not-exist").status_code == 404


# --- Approvers booking themselves --------------------------------------------------------


@pytest.mark.parametrize("name", ["approver", "owner"])
def test_bookings_by_approvers_skip_the_approval(world, name):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    res = world["book"](world["api"][name], room["id"])
    assert res.status_code == 200, res.content
    event = res.json()
    assert event["status"] == "approved"
    assert event["decided_by"] == str(world["users"][name].id)
    assert not Notification.objects.filter(type="approval_requested", event_id=event["id"]).exists()
    assert world["api"]["owner"].get("/approvals").json() == []


def test_default_approver_still_asks_when_the_resource_has_its_own_approvers(world):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    add_resource_approver(world, room["id"], "resapprover")
    assert world["book"](world["api"]["approver"], room["id"]).json()["status"] == "pending"
    assert world["book"](world["api"]["resapprover"], room["id"], start=BASE + timedelta(hours=2)).json()["status"] == "approved"


def test_self_approved_booking_still_respects_conflicts(world):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    first = world["book"](world["api"]["approver"], room["id"]).json()
    assert first["status"] == "approved"
    assert world["book"](world["api"]["owner"], room["id"]).status_code == 409


def test_rescheduling_by_an_approver_keeps_the_approval(world):
    _, event = approved_booking(world)
    res = world["api"]["owner"].patch(f"/events/{event['id']}", {
        "start": iso(BASE + timedelta(days=1)),
        "end": iso(BASE + timedelta(days=1, hours=1)),
    })
    assert res.json()["status"] == "approved"


def test_approver_switching_resource_approves_it(world):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    hall = world["resource"]("Hall")
    event = world["book"](world["api"]["approver"], room["id"]).json()
    res = world["api"]["approver"].patch(f"/events/{event['id']}", {"resource_id": hall["id"]})
    assert res.json()["status"] == "approved"


# --- Who sees pending bookings -----------------------------------------------------------


def visible_titles(world, name):
    res = world["api"][name].get(
        f"/calendars/{world['cal']['id']}/events"
        f"?start={quote(iso(BASE - timedelta(days=1)))}&end={quote(iso(BASE + timedelta(days=1)))}"
    )
    assert res.status_code == 200, res.content
    return {e["title"] for e in res.json()}


def test_pending_bookings_are_only_listed_for_those_involved(world):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    world["book"](world["api"]["booker"], room["id"], title="Secret request")
    for name in ("booker", "approver", "owner"):
        assert "Secret request" in visible_titles(world, name), name
    for name in ("other", "editor", "resapprover"):
        assert "Secret request" not in visible_titles(world, name), name


def test_participants_see_the_pending_booking(world):
    room = world["resource"]("Room")
    event = world["book"](
        world["api"]["booker"], room["id"], title="With guest",
        participants=[{"user_id": str(world["users"]["other"].id)}],
    ).json()
    assert "With guest" in visible_titles(world, "other")
    assert world["api"]["other"].get(f"/events/{event['id']}").status_code == 200
    assert "With guest" not in visible_titles(world, "editor")


def test_pending_booking_is_hidden_from_uninvolved_members(world):
    room = world["resource"]("Room")
    event = world["book"](world["api"]["booker"], room["id"]).json()
    for url in (f"/events/{event['id']}", f"/events/{event['id']}/comments"):
        assert world["api"]["other"].get(url).status_code == 404
        assert world["api"]["editor"].get(url).status_code == 404


def test_approved_bookings_are_visible_to_everyone(world):
    room = world["resource"]("Room")
    event = world["book"](world["api"]["booker"], room["id"], title="Public now").json()
    world["api"]["owner"].post(f"/events/{event['id']}/approve")
    for name in ("other", "editor", "approver"):
        assert "Public now" in visible_titles(world, name), name


def test_can_decide_flag(world):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    event = world["book"](world["api"]["booker"], room["id"]).json()
    assert world["api"]["approver"].get(f"/events/{event['id']}").json()["can_decide"] is True
    assert world["api"]["owner"].get(f"/events/{event['id']}").json()["can_decide"] is True
    assert world["api"]["booker"].get(f"/events/{event['id']}").json()["can_decide"] is False
    world["api"]["approver"].post(f"/events/{event['id']}/approve")
    assert world["api"]["approver"].get(f"/events/{event['id']}").json()["can_decide"] is False


# --- Notifications -----------------------------------------------------------------------


def test_request_and_invitation_notifications_cannot_be_deleted(world):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    event = world["book"](
        world["api"]["booker"], room["id"], participants=[{"user_id": str(world["users"]["other"].id)}],
    ).json()
    request_note = Notification.objects.get(user=world["users"]["approver"], type="approval_requested")
    invite = Notification.objects.get(user=world["users"]["other"], type="participant_added")
    assert world["api"]["approver"].delete(f"/notifications/{request_note.id}").status_code == 400
    assert world["api"]["other"].delete(f"/notifications/{invite.id}").status_code == 400

    world["api"]["approver"].post(f"/events/{event['id']}/approve")
    outcome = Notification.objects.get(user=world["users"]["booker"], type="booking_approved")
    assert world["api"]["booker"].delete(f"/notifications/{outcome.id}").status_code == 200


def test_notification_groups_and_live_status(world):
    add_default_approver(world, "approver")
    room = world["resource"]("Room")
    event = world["book"](
        world["api"]["booker"], room["id"], participants=[{"user_id": str(world["users"]["approver"].id)}],
    ).json()
    api = world["api"]["approver"]

    approvals = api.get("/notifications?group=approvals").json()
    assert [n["type"] for n in approvals] == ["approval_requested"]
    assert approvals[0]["event_status"] == "pending"
    assert approvals[0]["deletable"] is False
    invitations = api.get("/notifications?group=invitations").json()
    assert [n["type"] for n in invitations] == ["participant_added"]
    assert invitations[0]["response_status"] == "needs_action"
    all_types = {n["type"] for n in api.get("/notifications").json()}
    assert {"approval_requested", "participant_added", "member_added"} <= all_types
    assert api.get("/notifications?group=nope").status_code == 422
    assert api.get("/notifications/open-counts").json() == {"approvals": 1, "invitations": 1}

    api.post(f"/events/{event['id']}/approve")
    assert api.get("/notifications?group=approvals").json()[0]["event_status"] == "approved"
    assert api.get("/notifications/open-counts").json()["approvals"] == 0


# --- CalDAV ------------------------------------------------------------------------------


def test_caldav_only_shares_confirmed_and_approved_events(world):
    from core.caldav.storage import _SHARED_STATUSES

    assert _SHARED_STATUSES == {"confirmed", "approved"}
