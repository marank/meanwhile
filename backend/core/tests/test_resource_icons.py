"""Resources can have an icon, which events and the resource pickers show before the name."""

from datetime import timedelta

import pytest

from core.tests.test_approval_workflow import BASE, iso, world  # noqa: F401

pytestmark = pytest.mark.django_db


def occurrences_of(api, cal):
    start, end = (iso(BASE + timedelta(days=d)).replace("+", "%2B") for d in (-1, 1))
    return api.get(f"/events?calendar_ids={cal['id']}&start={start}&end={end}").json()


def test_a_resource_has_an_icon(world):
    projector = world["resource"]("Projector", requires_approval=False, icon="projector")
    assert projector["icon"] == "projector"
    assert world["resource"]("Plain", requires_approval=False)["icon"] == ""

    api, cal = world["api"]["full"], world["cal"]
    # Changing the icon, or taking it away (an editor may).
    url = f"/calendars/{cal['id']}/resources/{projector['id']}"
    assert api.patch(url, {"icon": "door-open"}).json()["icon"] == "door-open"
    assert api.patch(url, {"name": "Beamer"}).json()["icon"] == "door-open"
    assert api.patch(url, {"icon": ""}).json()["icon"] == ""


@pytest.mark.parametrize("icon", ["Door", "door open", "door--open", "-door", "<svg>", "x" * 41])
def test_icon_names_are_checked(world, icon):
    cal = world["cal"]
    res = world["api"]["full"].post(f"/calendars/{cal['id']}/resources", {"name": "R", "icon": icon})
    assert res.status_code == 422


def test_searches_and_occurrences_carry_the_icon(world):
    resource = world["resource"]("Projector", requires_approval=False, icon="projector")
    room = world["resource"]("Room", requires_approval=False, icon="door-open", is_location=True)
    cal, api = world["cal"], world["api"]["booker"]

    found = api.get(f"/search?entity=resources&calendar_id={cal['id']}").json()
    assert [r["meta"]["icon"] for r in found] == ["projector"]
    found = api.get(f"/search?entity=locations&calendar_id={cal['id']}").json()
    assert [r["meta"]["icon"] for r in found] == ["door-open"]

    res = api.post(
        f"/calendars/{cal['id']}/events",
        {
            "title": "Meeting",
            "start": iso(BASE),
            "end": iso(BASE + timedelta(hours=1)),
            "resource_id": resource["id"],
            "location_resource_id": room["id"],
        },
    )
    assert res.status_code == 200
    occurrences = occurrences_of(api, cal)
    assert [(o["resource_icon"], o["location_resource_icon"]) for o in occurrences] == [("projector", "door-open")]

    plain = api.post(
        f"/calendars/{cal['id']}/events",
        {"title": "Plain", "start": iso(BASE + timedelta(hours=3)), "end": iso(BASE + timedelta(hours=4))},
    )
    assert plain.status_code == 200
    occurrences = occurrences_of(api, cal)
    assert sorted((o["resource_icon"], o["location_resource_icon"]) for o in occurrences) == [("", ""), ("projector", "door-open")]
