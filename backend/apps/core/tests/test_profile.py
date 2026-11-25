"""
The signed-in user's own settings (/users/me).
"""

import pytest

from apps.core.tests.helpers import Api, make_user

pytestmark = pytest.mark.django_db


def test_the_day_starts_at_nine_until_the_user_chooses_another_hour() -> None:
    api = Api(make_user("ann"))
    assert api.get("/users/me").json()["day_start"] == 9
    res = api.patch("/users/me", {"day_start": 7})
    assert res.status_code == 200, res.content
    assert res.json()["day_start"] == 7
    assert api.get("/users/me").json()["day_start"] == 7


@pytest.mark.parametrize("hour", [-1, 24])
def test_the_day_starts_within_the_day(hour: int) -> None:
    api = Api(make_user("ann"))
    assert api.patch("/users/me", {"day_start": hour}).status_code == 422
