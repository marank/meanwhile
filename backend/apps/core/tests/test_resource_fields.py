"""
The fields of a resource: what creating and changing one accepts.
"""

import pytest

from apps.core.tests.helpers import World

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("color", [None, "red", "#12345", "#1234567", "#gggggg"])
def test_a_new_resource_needs_a_hex_color(world: World, color: str | None) -> None:
    cal = world["cal"]
    res = world["api"]["full"].post(f"/calendars/{cal['id']}/resources", {"name": "R", "color": color})
    assert res.status_code == 422


def test_a_new_resource_without_color_gets_the_default(world: World) -> None:
    cal = world["cal"]
    res = world["api"]["full"].post(f"/calendars/{cal['id']}/resources", {"name": "R"})
    assert res.status_code == 200, res.content
    assert res.json()["color"] == "#f59e0b"


@pytest.mark.parametrize("field", ["name", "color", "icon", "requires_approval", "is_location", "is_active"])
def test_changing_a_field_to_null_is_refused(world: World, field: str) -> None:
    resource = world["resource"]("Projector", requires_approval=False)
    url = f"/calendars/{world['cal']['id']}/resources/{resource['id']}"

    res = world["api"]["owner"].patch(url, {field: None})

    assert res.status_code == 422, res.content
    assert world["api"]["owner"].patch(url, {"color": "#123abc"}).json()["color"] == "#123abc"
