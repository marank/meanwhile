"""
Tests for the endpoints that let the frontend replace several requests with one.
"""

from datetime import timedelta

import pytest

from core.models import EventParticipant, ResourceApprover
from core.tests.helpers import BASE, Api, iso

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

    group = api.post("/groups", {"name": "Staff", "member_ids": [str(u["full"].id), str(u["booker"].id)]}).json()
    assert group["member_count"] == 2

    group = api.patch(f"/groups/{group['id']}", {"member_ids": [str(u["booker"].id)]}).json()
    assert group["member_count"] == 1
    members = api.get(f"/groups/{group['id']}").json()["members"]
    assert [m["id"] for m in members] == [str(u["booker"].id)]


def test_approvers_are_set_as_a_whole_list(world):
    u, owner = world["users"], world["api"]["owner"]
    path = f"/calendars/{world['cal']['id']}/resources"
    resource = world["resource"]("Room", approver_ids=[str(u["approver"].id)])
    assert [a["user_id"] for a in resource["approvers"]] == [str(u["approver"].id)]

    res = owner.put(f"{path}/{resource['id']}/approvers", {"user_ids": [str(u["resapprover"].id), str(u["resapprover"].id)]})
    assert res.status_code == 200, res.content
    assert [a["user_id"] for a in res.json()] == [str(u["resapprover"].id)]
    assert [a["user_id"] for a in owner.get(f"{path}/{resource['id']}/approvers").json()] == [str(u["resapprover"].id)]
    # The resource lists them, too.
    listed = {r["id"]: r for r in owner.get(path).json()}
    assert [a["user_id"] for a in listed[resource["id"]]["approvers"]] == [str(u["resapprover"].id)]

    assert owner.put(f"{path}/{resource['id']}/approvers", {"user_ids": []}).json() == []
    assert not ResourceApprover.objects.exists()


def test_the_calendars_default_approvers_work_the_same_way(world):
    u, owner = world["users"], world["api"]["owner"]
    path = f"/calendars/{world['cal']['id']}/approvers"
    assert owner.get(path).json() == []
    res = owner.put(path, {"user_ids": [str(u["approver"].id), str(u["full"].id)]})
    assert res.status_code == 200, res.content
    assert sorted(a["user_id"] for a in res.json()) == sorted([str(u["approver"].id), str(u["full"].id)])
    assert {"email", "display_name"} <= set(res.json()[0])

    assert [a["user_id"] for a in owner.put(path, {"user_ids": [str(u["full"].id)]}).json()] == [str(u["full"].id)]
    # Only the owner manages them.
    assert world["api"]["full"].get(path).status_code == 403
    assert world["api"]["full"].put(path, {"user_ids": []}).status_code == 403
    assert world["api"]["outsider"].put(path, {"user_ids": []}).status_code == 403


def test_approvers_must_be_members(world):
    owner, outsider = world["api"]["owner"], str(world["users"]["outsider"].id)
    resource = world["resource"]("Room")
    cal = world["cal"]["id"]
    assert owner.put(f"/calendars/{cal}/resources/{resource['id']}/approvers", {"user_ids": [outsider]}).status_code == 400
    assert owner.put(f"/calendars/{cal}/approvers", {"user_ids": [outsider]}).status_code == 400
    assert owner.put(f"/calendars/{cal}/approvers", {"user_ids": ["no-such-user"]}).status_code == 400
    assert not ResourceApprover.objects.exists()
