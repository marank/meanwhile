"""
Cross-user and cross-calendar isolation: an id from one tenant must never reach another's data.

These lock in the authorization review. Each test takes the attacker's side — it uses a real id
from one user or calendar and asserts that someone who should not reach it is turned away (403/404),
or, where the endpoint deletes by a user/calendar-scoped filter, that the target survives untouched.
"""

from typing import Any

import pytest

from apps.core.tests.helpers import BASE, World, iso

pytestmark = pytest.mark.django_db


@pytest.fixture
def foreign(world: World) -> dict[str, Any]:
    """A second calendar the `outsider` owns, with a category, a resource and an event of its own.

    `outsider` is a member of nothing in `world`, so every id here belongs to a tenant the `world`
    members have no access to, and vice versa.
    """
    api = world["api"]["outsider"]
    cal = api.post("/calendars", {"name": "Private"}).json()
    category = api.post(f"/calendars/{cal['id']}/categories", {"name": "Secret"}).json()
    resource = api.post(f"/calendars/{cal['id']}/resources", {"name": "Desk", "requires_approval": False}).json()
    event = api.post(
        f"/calendars/{cal['id']}/events",
        {"title": "Private", "start": iso(BASE), "end": iso(BASE.replace(hour=10))},
    ).json()
    return {"cal": cal, "category": category, "resource": resource, "event": event}


def test_a_foreign_event_and_its_subresources_are_invisible(world: World, foreign: dict[str, Any]) -> None:
    """A non-member reading a foreign event by id gets 404, as if it did not exist — for the event
    and every sub-resource hung off it."""
    owner = world["api"]["owner"]
    eid = foreign["event"]["id"]
    for path in ("", "/comments", "/participants", "/activity", "/reminders"):
        res = owner.get(f"/events/{eid}{path}")
        assert res.status_code == 404, (path, res.status_code)


def test_a_non_member_cannot_change_or_delete_a_foreign_event(world: World, foreign: dict[str, Any]) -> None:
    owner = world["api"]["owner"]
    eid = foreign["event"]["id"]
    assert owner.patch(f"/events/{eid}", {"title": "Hijacked"}).status_code == 403
    assert owner.delete(f"/events/{eid}").status_code == 403
    # Untouched for its owner.
    assert world["api"]["outsider"].get(f"/events/{eid}").json()["title"] == "Private"


def test_a_non_member_is_refused_on_a_foreign_calendar(world: World, foreign: dict[str, Any]) -> None:
    owner = world["api"]["owner"]
    cal = foreign["cal"]["id"]
    reads = [
        f"/calendars/{cal}",
        f"/calendars/{cal}/members",
        f"/calendars/{cal}/categories",
        f"/calendars/{cal}/resources",
        f"/calendars/{cal}/feed-url",
        f"/calendars/{cal}/approvers",
        f"/calendars/{cal}/groups",
    ]
    for path in reads:
        assert owner.get(path).status_code == 403, path
    assert owner.post(f"/calendars/{cal}/feed-token/rotate").status_code == 403
    assert owner.delete(f"/calendars/{cal}").status_code == 403


def test_a_category_id_from_another_calendar_is_not_reachable(world: World, foreign: dict[str, Any]) -> None:
    """Pairing one's own calendar id with a category id from another calendar must not reach it."""
    owner, cal = world["api"]["owner"], world["cal"]["id"]
    alien = foreign["category"]["id"]
    assert owner.patch(f"/calendars/{cal}/categories/{alien}", {"name": "x"}).status_code == 404
    # delete scopes by (id, calendar); nothing matches, so the foreign category survives.
    owner.delete(f"/calendars/{cal}/categories/{alien}")
    survivors = {c["id"] for c in world["api"]["outsider"].get(f"/calendars/{foreign['cal']['id']}/categories").json()}
    assert alien in survivors


def test_a_resource_from_another_calendar_cannot_be_booked(world: World, foreign: dict[str, Any]) -> None:
    booker, cal = world["api"]["booker"], world["cal"]["id"]
    res = booker.post(
        f"/calendars/{cal}/events",
        {
            "title": "Steal the desk",
            "start": iso(BASE),
            "end": iso(BASE.replace(hour=10)),
            "resource_id": foreign["resource"]["id"],
        },
    )
    assert res.status_code == 404


def test_a_member_cannot_change_or_remove_another_participant(world: World) -> None:
    """`other` is a member, but with "own" rights and not the event's creator, so it may touch only
    its own participation — not someone else's."""
    booker, other = world["api"]["booker"], world["api"]["other"]
    event = booker.post(
        f"/calendars/{world['cal']['id']}/events",
        {"title": "Booking", "start": iso(BASE), "end": iso(BASE.replace(hour=10))},
    ).json()
    participant = booker.post(f"/events/{event['id']}/participants", {"user_id": str(world["users"]["full"].id)}).json()
    patch = other.patch(f"/events/{event['id']}/participants/{participant['id']}", {"status": "accepted"})
    assert patch.status_code == 403
    assert other.delete(f"/events/{event['id']}/participants/{participant['id']}").status_code == 403


def test_a_member_cannot_cancel_another_users_event(world: World) -> None:
    booker, other = world["api"]["booker"], world["api"]["other"]
    event = world["book"](booker, None).json()
    assert other.post(f"/events/{event['id']}/cancel").status_code == 403


def test_a_member_who_is_not_an_approver_cannot_decide(world: World) -> None:
    """Membership alone does not let someone approve or reject a pending booking; that needs the
    approver role for the booked resource."""
    room = world["resource"]("Room", approver_ids=[str(world["users"]["resapprover"].id)])
    event = world["book"](world["api"]["booker"], room["id"]).json()
    assert event["status"] == "pending"
    other = world["api"]["other"]
    assert other.post(f"/events/{event['id']}/approve").status_code == 403
    assert other.post(f"/events/{event['id']}/reject").status_code == 403


def test_a_notification_belongs_only_to_its_user(world: World) -> None:
    booker = world["api"]["booker"]
    event = world["book"](booker, None).json()
    booker.post(f"/events/{event['id']}/participants", {"user_id": str(world["users"]["other"].id)})
    notifications = world["api"]["other"].get("/notifications").json()
    assert notifications, "the invited user should have been notified"
    nid = notifications[0]["id"]
    outsider = world["api"]["outsider"]
    assert outsider.post(f"/notifications/{nid}/read").status_code == 404
    assert outsider.delete(f"/notifications/{nid}").status_code == 404
    # Still there, still unread, for the user it belongs to.
    assert world["api"]["other"].post(f"/notifications/{nid}/read").status_code == 200


def test_a_calendar_cannot_be_moved_into_another_users_folder(world: World) -> None:
    """A folder id is private to its user; naming someone else's as a parent is 404, not a silent move."""
    owner, full = world["api"]["owner"], world["api"]["full"]
    folder = owner.post("/layout/folders", {"name": "Owner's", "position": 0}).json()
    res = full.patch(
        "/layout/items",
        {"items": [{"type": "calendar", "id": world["cal"]["id"], "parent_id": folder["id"], "position": 0}]},
    )
    assert res.status_code == 404


def test_an_app_password_belongs_only_to_its_user(world: World) -> None:
    owner = world["api"]["owner"]
    created = owner.post("/users/me/app-passwords", {"label": "CalDAV"}).json()
    # The delete scopes by the caller's own passwords, so another user's call removes nothing.
    world["api"]["full"].delete(f"/users/me/app-passwords/{created['id']}")
    labels = {p["label"] for p in owner.get("/users/me/app-passwords").json()}
    assert "CalDAV" in labels
