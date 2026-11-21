"""
The footer of every email (who it went to, why, the links), and unsubscribing by its link.
"""

import email.policy
import re
from datetime import timedelta
from typing import get_args

import pytest
from django.core import mail as django_mail
from django.core.mail import EmailMessage
from django.test import Client
from pytest_django.fixtures import Settings

from apps.core.models import Notification, User
from apps.core.schemas import EmailKind
from apps.core.services.notifications import EMAIL_KINDS
from apps.core.services.unsubscribe import make_token
from apps.core.tests.helpers import BASE, World, iso

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def empty_outbox(world: World) -> None:
    django_mail.outbox.clear()


def to(address: str) -> list[EmailMessage]:
    return [m for m in django_mail.outbox if m.to == [address]]


def comment(world: World, body: str = "Bring the slides") -> None:
    res = world["api"]["owner"].post(
        f"/calendars/{world['cal']['id']}/events",
        {"title": "Planning", "start": iso(BASE), "end": iso(BASE + timedelta(hours=1))},
    )
    world["api"]["other"].post(f"/events/{res.json()['id']}/comments", {"body": body})


def unsubscribe_link(message: EmailMessage, label: str = "Unsubscribe from all emails of this kind") -> str:
    """The token of the footer's link with `label`."""
    match = re.search(rf"{label}: \S+/unsubscribe/(\S+)", str(message.body))
    assert match is not None
    return match.group(1)


def test_emails_say_whom_they_went_to_why_and_where_to_choose_them(world: World) -> None:
    comment(world)
    [message] = to("owner@example.test")
    body = str(message.body)
    footer = body.split("\n-- \n")[1]
    assert footer.startswith(
        "Sent to owner@example.test. You get this email because you created or commented on this event."
    )
    assert "Email settings: http://app.test/account?tab=emailNotifications" in footer
    assert "No more emails about this event: http://app.test/unsubscribe/" in footer
    assert "Unsubscribe from all emails of this kind: http://app.test/unsubscribe/" in footer
    assert "Open Meanwhile: http://app.test/" in footer
    # Mail programs offer to unsubscribe with one click (RFC 8058).
    token = unsubscribe_link(message)
    assert message.extra_headers["List-Unsubscribe"] == f"<http://app.test/api/unsubscribe/{token}>"
    assert message.extra_headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_the_unsubscribe_header_goes_out_as_a_plain_address(world: World) -> None:
    comment(world)
    message = to("owner@example.test")[0]
    # As the SMTP backend writes it: long as it is, the address stays readable (not =?utf-8?q?...?=).
    raw = message.message(policy=email.policy.SMTP).as_bytes().decode()
    [header] = [line for line in raw.splitlines() if line.startswith("List-Unsubscribe:")]
    assert header == f"List-Unsubscribe: {message.extra_headers['List-Unsubscribe']}"
    assert "List-Unsubscribe-Post: List-Unsubscribe=One-Click" in raw


def test_guests_without_an_account_get_no_settings_or_unsubscribing(world: World) -> None:
    owner = world["api"]["owner"]
    event = owner.post(
        f"/calendars/{world['cal']['id']}/events",
        {"title": "Planning", "start": iso(BASE), "end": iso(BASE + timedelta(hours=1))},
    ).json()
    owner.post(f"/events/{event['id']}/participants", {"email": "guest@elsewhere.test"})
    [message] = to("guest@elsewhere.test")
    footer = str(message.body).split("\n-- \n")[1].strip()
    assert footer == "Sent to guest@elsewhere.test. You get this email because Owner invited you to this event."
    assert "List-Unsubscribe" not in message.extra_headers


def test_account_emails_lead_into_the_app_but_cannot_be_unsubscribed(world: World, settings: Settings) -> None:
    Client().post(
        "/api/auth/v1/auth/password/request", {"email": "other@example.test"}, content_type="application/json"
    )
    [message] = to("other@example.test")
    footer = str(message.body).split("\n-- \n")[1]
    assert "because a new password for Meanwhile was requested for this address" in footer
    assert "Open Meanwhile: http://app.test/" in footer
    assert "/unsubscribe/" not in footer
    assert "List-Unsubscribe" not in message.extra_headers


def test_the_link_unsubscribes_from_that_kind_only_once_confirmed(world: World) -> None:
    comment(world)
    token = unsubscribe_link(to("owner@example.test")[0])
    page = Client()
    # Opening it (as mail scanners do) changes nothing.
    res = page.get(f"/api/unsubscribe/{token}")
    assert res.json() == {"email": "owner@example.test", "kind": "comments", "event_title": None, "subscribed": True}
    res = page.post(f"/api/unsubscribe/{token}")
    assert res.status_code == 200
    assert res.json()["subscribed"] is False

    django_mail.outbox.clear()
    comment(world, "Once more")
    assert to("owner@example.test") == []
    prefs = world["api"]["owner"].get("/users/me").json()["email_notifications"]
    assert prefs["comments"] is False
    assert prefs["approvals"] is True
    # The page can take it back.
    assert page.delete(f"/api/unsubscribe/{token}").json()["subscribed"] is True


def test_mail_programs_unsubscribe_with_one_click(world: World) -> None:
    comment(world)
    message = to("owner@example.test")[0]
    url = message.extra_headers["List-Unsubscribe"].strip("<>").removeprefix("http://app.test")
    # A plain form post, without session or CSRF token.
    res = Client(enforce_csrf_checks=True).post(
        url, "List-Unsubscribe=One-Click", content_type="application/x-www-form-urlencoded"
    )
    assert res.status_code == 200, res.content
    assert User.objects.get(email="owner@example.test").email_notifications["comments"] is False


def test_made_up_or_foreign_links_do_nothing(world: World) -> None:
    owner = User.objects.get(email="owner@example.test")
    for token in ("nonsense", make_token(owner, "everything"), make_token(owner, "comments")[:-2] + "xx"):
        assert Client().get(f"/api/unsubscribe/{token}").status_code == 404
        assert Client().post(f"/api/unsubscribe/{token}").status_code == 404
    owner.refresh_from_db()
    assert not owner.email_notifications


def test_the_api_names_every_kind_of_email() -> None:
    assert set(get_args(EmailKind)) == set(EMAIL_KINDS)


def test_the_event_link_stops_its_emails_only_and_can_be_undone(world: World) -> None:
    owner = world["api"]["owner"]
    event = owner.post(
        f"/calendars/{world['cal']['id']}/events",
        {"title": "Planning", "start": iso(BASE), "end": iso(BASE + timedelta(hours=1))},
    ).json()
    other = User.objects.get(email="other@example.test")
    owner.post(f"/events/{event['id']}/participants", {"user_id": str(other.id), "email": other.email})
    [invitation] = to(other.email)
    # Having commented, they hear of the comments after theirs.
    world["api"]["other"].post(f"/events/{event['id']}/comments", {"body": "Count me in"})
    token = unsubscribe_link(invitation, "No more emails about this event")
    res = Client().get(f"/api/unsubscribe/{token}")
    assert res.json() == {"email": other.email, "kind": None, "event_title": "Planning", "subscribed": True}
    assert Client().post(f"/api/unsubscribe/{token}").json()["subscribed"] is False

    django_mail.outbox.clear()
    owner.patch(
        f"/events/{event['id']}",
        {"title": "Planning (moved)", "start": iso(BASE + timedelta(hours=2)), "end": iso(BASE + timedelta(hours=3))},
    )
    world["api"]["full"].post(f"/events/{event['id']}/comments", {"body": "Fine"})
    assert to(other.email) == []
    # The app still tells, and other events still come by email.
    assert Notification.objects.filter(user=other, type="comment_added").exists()
    django_mail.outbox.clear()
    comment(world)
    assert len(to("owner@example.test")) == 1

    # The page can take it back.
    assert Client().delete(f"/api/unsubscribe/{token}").json()["subscribed"] is True
    django_mail.outbox.clear()
    world["api"]["full"].post(f"/events/{event['id']}/comments", {"body": "Again"})
    assert len(to(other.email)) == 1
