"""
Removing a member from a calendar also removes them as an approver, unless they still have access.
"""

import pytest

from core.models import CalendarApprover, CalendarGroup, ResourceApprover, UserGroup

pytestmark = pytest.mark.django_db


def make_approver(world, user):
    path = f"/calendars/{world['cal']['id']}/approvers"
    owner = world["api"]["owner"]
    current = [a["user_id"] for a in owner.get(path).json()]
    assert owner.put(path, {"user_ids": [*current, str(user.id)]}).status_code == 200


def approver_rows(world, user):
    return (
        CalendarApprover.objects.filter(calendar_id=world["cal"]["id"], user=user).count(),
        ResourceApprover.objects.filter(resource__calendar_id=world["cal"]["id"], user=user).count(),
    )


def test_a_removed_member_is_no_approver_any_more(world):
    owner, user = world["api"]["owner"], world["users"]["approver"]
    world["resource"]("Room", approver_ids=[str(user.id)])
    make_approver(world, user)
    assert approver_rows(world, user) == (1, 1)

    assert owner.delete(f"/calendars/{world['cal']['id']}/members/{user.id}").status_code == 200
    assert approver_rows(world, user) == (0, 0)
    # The calendar's other approvers are untouched.
    other = world["users"]["resapprover"]
    make_approver(world, other)
    assert approver_rows(world, other) == (1, 0)


def test_someone_who_keeps_access_through_a_group_stays_an_approver(world):
    owner, user = world["api"]["owner"], world["users"]["approver"]
    group = UserGroup.objects.create(name="Crew")
    user.groups.add(group)
    CalendarGroup.objects.create(calendar_id=world["cal"]["id"], group=group, role="read")
    make_approver(world, user)

    assert owner.delete(f"/calendars/{world['cal']['id']}/members/{user.id}").status_code == 200
    assert approver_rows(world, user) == (1, 0)
