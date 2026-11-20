"""
The storage plugin, called as Radicale calls it.
"""

import pytest
from radicale import config

from apps.core.caldav.storage import Collection, Storage, acting_as
from apps.core.models import Calendar
from apps.core.tests.helpers import make_user

pytestmark = pytest.mark.django_db


def test_a_principal_is_returned_as_radicale_unpacks_it() -> None:
    # Radicale creates a missing principal with `new_coll, _, _ = storage.create_collection(path)`.
    user = make_user("someone")
    with acting_as(user.email):
        principal, replaced, new_hrefs = Storage(config.load()).create_collection(f"/{user.email}/")
    assert isinstance(principal, Collection) and principal.is_principal
    assert (replaced, new_hrefs) == ({}, [])


def test_a_new_calendar_is_returned_as_radicale_expects() -> None:
    user = make_user("someone")
    with acting_as(user.email):
        collection, replaced, new_hrefs = Storage(config.load()).create_collection(
            f"/{user.email}/work/", props={"tag": "VCALENDAR", "D:displayname": "Work"}
        )
    assert isinstance(collection, Collection)
    assert collection.get_meta("D:displayname") == "Work"
    assert Calendar.objects.get(owner=user, dav_name="work").name == "Work"
    assert (replaced, new_hrefs) == ({}, [])
