"""
Tests for the endpoints that let the frontend replace several requests with one.
"""

from datetime import timedelta

import pytest

from core.models import EventParticipant, ResourceApprover
from core.tests.test_approval_workflow import BASE, Api, iso, world  # noqa: F401 (fixture)

pytestmark = pytest.mark.django_db


def test_events_of_several_calendars_in_one_request(world):
    owner = world["api"]["owner"]
    second = owner.post("/calendars", {"name": "Second"}).json()
    world["book"](owner, None, title="Team event")
    owner.post(f"/calendars/{second['id']}/events", {
        "title": "Second event",
        "start": iso(BASE + timedelta(hours=2)),
        "end": iso(BASE + timedelta(hours=3)),
    })

    res = owner.get(
        f"/events?calendar_ids={world['cal']['id']}&calendar_ids={second['id']}"
        f"&start={iso(BASE - timedelta(days=1)).replace('+', '%2B')}"
        f"&end={iso(BASE + timedelta(days=1)).replace('+', '%2B')}"
    )
    assert res.status_code == 200, res.content
    assert [o["title"] for o in res.json()] == ["Team event", "Second event"]


def test_events_of_unreadable_calendars_are_skipped(world):
    outsider = world["api"]["outsider"]
    world["book"](world["api"]["owner"], None)
    res = outsider.get(
        f"/events?calendar_ids={world['cal']['id']}"
        f"&start={iso(BASE - timedelta(days=1)).replace('+', '%2B')}"
        f"&end={iso(BASE + timedelta(days=1)).replace('+', '%2B')}"
    )
    assert res.status_code == 200, res.content
    assert res.json() == []


def test_participant_answers_own_invitation(world):
    owner = world["api"]["owner"]
    other = world["users"]["other"]
    event = world["book"](owner, None, participants=[{"user_id": str(other.id)}]).json()

    res = world["api"]["other"].patch(f"/events/{event['id']}/participants/me", {"status": "accepted"})
    assert res.status_code == 200, res.content
    assert EventParticipant.objects.get(event_id=event["id"], user=other).status == "accepted"


def test_answering_requires_an_invitation(world):
    event = world["book"](world["api"]["owner"], None).json()
    res = world["api"]["booker"].patch(f"/events/{event['id']}/participants/me", {"status": "accepted"})
    assert res.status_code == 404


def test_group_members_are_set_in_one_request(world):
    owner = world["users"]["owner"]
    owner.is_admin = True
    owner.save()
    api = Api(owner)
    u = world["users"]

    group = api.post("/groups", {"name": "Staff", "member_ids": [str(u["editor"].id), str(u["booker"].id)]}).json()
    assert group["member_count"] == 2

    group = api.patch(f"/groups/{group['id']}", {"member_ids": [str(u["booker"].id)]}).json()
    assert group["member_count"] == 1
    members = api.get(f"/groups/{group['id']}").json()["members"]
    assert [m["id"] for m in members] == [str(u["booker"].id)]


def test_resource_approvers_are_set_in_one_request(world):
    u = world["users"]
    resource = world["resource"]("Room", approver_ids=[str(u["approver"].id)])
    assert [a["user_id"] for a in resource["approvers"]] == [str(u["approver"].id)]

    res = world["api"]["owner"].patch(
        f"/calendars/{world['cal']['id']}/resources/{resource['id']}",
        {"approver_ids": [str(u["resapprover"].id)]},
    )
    assert res.status_code == 200, res.content
    assert list(ResourceApprover.objects.filter(resource_id=resource["id"]).values_list("user_id", flat=True)) == [
        u["resapprover"].id
    ]


def test_resource_approvers_must_be_members(world):
    res = world["api"]["owner"].post(
        f"/calendars/{world['cal']['id']}/resources",
        {"name": "Room", "approver_ids": [str(world["users"]["outsider"].id)]},
    )
    assert res.status_code == 400
    assert not ResourceApprover.objects.exists()
