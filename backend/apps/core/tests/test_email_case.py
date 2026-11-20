"""
Email addresses are the usernames and are unique regardless of case.
"""

import pytest
from django.contrib.auth import authenticate
from django.db import IntegrityError

from apps.core.models import User
from apps.core.tests.helpers import BASE, World, iso

pytestmark = pytest.mark.django_db


def test_two_users_cannot_share_an_email_in_different_case() -> None:
    User.objects.create_user(email="Anna@example.test", display_name="Anna")
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="anna@example.test", display_name="Anna")


def test_signing_in_ignores_the_case_of_the_email() -> None:
    user = User.objects.create_user(email="Anna@example.test", password="secret-enough", display_name="Anna")
    assert authenticate(username="anna@EXAMPLE.test", password="secret-enough") == user


def test_a_participant_added_by_email_is_linked_to_the_user_in_any_case(world: World) -> None:
    booker, full = world["api"]["booker"], world["users"]["full"]
    full.email = full.email.title()
    full.save()
    event = booker.post(
        f"/calendars/{world['cal']['id']}/events",
        {"title": "Booking", "start": iso(BASE), "end": iso(BASE.replace(hour=10))},
    ).json()
    participant = booker.post(f"/events/{event['id']}/participants", {"email": full.email.lower()}).json()
    assert participant["user_id"] == str(full.id)
