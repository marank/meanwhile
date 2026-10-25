"""
Emails: notifications by email, and scheduling by email (iMIP): invitations, their changes and
cancellations, and the participants' answers by link or from their mail programs.
"""

import base64
import re
from datetime import datetime, timedelta
from html import unescape
from io import StringIO
from pathlib import Path
from typing import Any

import icalendar
import pytest
from django.core import mail as django_mail
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.core.management import call_command
from django.test import Client
from pytest_django.fixtures import Settings

from core.models import Event, EventParticipant, Notification
from core.services.itip import process_email, process_itip
from core.tests.helpers import BASE, World, iso

pytestmark = pytest.mark.django_db

GUEST = "guest@elsewhere.test"


@pytest.fixture(autouse=True)
def empty_outbox(world: World) -> None:
    """Without the emails of setting the calendar up (members are told they were added)."""
    django_mail.outbox.clear()


def create(world: World, user: str = "owner", **fields: Any) -> dict[str, Any]:
    data = {
        "title": "Planning",
        "start": iso(BASE),
        "end": iso(BASE + timedelta(hours=1)),
        "timezone": "Europe/Berlin",
        **fields,
    }
    res = world["api"][user].post(f"/calendars/{world['cal']['id']}/events", data)
    assert res.status_code == 200, res.content
    event: dict[str, Any] = res.json()
    return event


def invite(world: World, event: dict[str, Any], email: str = GUEST, user: str = "owner") -> dict[str, Any]:
    res = world["api"][user].post(f"/events/{event['id']}/participants", {"email": email})
    assert res.status_code == 200, res.content
    participant: dict[str, Any] = res.json()
    return participant


def to(address: str) -> list[EmailMessage]:
    return [m for m in django_mail.outbox if m.to == [address]]


def itip(message: EmailMessage) -> tuple[str, icalendar.Component]:
    """The METHOD and the VEVENT of the iTIP message an email carries inline."""
    assert isinstance(message, EmailMultiAlternatives)
    ical = next(content for content, mimetype in message.alternatives if mimetype.startswith("text/calendar"))
    assert isinstance(ical, str | bytes)
    cal = icalendar.Calendar.from_ical(ical)
    return str(cal["METHOD"]), cal.walk("VEVENT")[0]


def reply(
    participant_email: str,
    uid: str,
    partstat: str,
    sender: str | None = None,
    organizer: str = "owner@example.test",
    **extra: str,
) -> bytes:
    vevent = icalendar.Event()
    vevent.add("uid", uid)
    vevent.add("dtstamp", BASE)
    vevent.add("organizer", f"mailto:{organizer}")
    vevent.add(
        "attendee", icalendar.vCalAddress(f"mailto:{participant_email}"), parameters={"PARTSTAT": partstat, **extra}
    )
    cal = icalendar.Calendar()
    cal.add("prodid", "-//Test//EN")
    cal.add("version", "2.0")
    cal.add("method", "REPLY")
    cal.add_component(vevent)
    message = EmailMessage("Accepted", "", sender or participant_email, [organizer])
    message.attach("invite.ics", cal.to_ical().decode(), "text/calendar; method=REPLY")
    return message.message().as_bytes()


def status_of(event: dict[str, Any], email: str = GUEST) -> str:
    return EventParticipant.objects.get(event_id=event["id"], email=email).status


# Invitations -----------------------------------------------------------------------------------


def test_invited_guests_get_the_event_as_request_with_links_to_answer(world: World) -> None:
    event = create(world)
    invite(world, event)
    [message] = to(GUEST)
    assert message.subject.startswith("Invitation: Planning @ ")
    assert "Owner" in message.from_email
    assert message.reply_to == ["owner@example.test"]
    method, vevent = itip(message)
    assert method == "REQUEST"
    assert str(vevent["UID"]) == event["uid"]
    assert str(vevent["ORGANIZER"]) == "mailto:owner@example.test"
    attendee = vevent["ATTENDEE"]
    assert str(attendee) == f"mailto:{GUEST}"
    assert attendee.params["PARTSTAT"] == "NEEDS-ACTION" and attendee.params["RSVP"] == "TRUE"
    # Also as a file, for mail programs that don't show invitations.
    assert [a[0] for a in message.attachments] == ["invite.ics"]
    token = EventParticipant.objects.get(email=GUEST).rsvp_token
    assert f"http://app.test/event/{token}?answer=accepted" in message.body
    # A link to see the whole event, for guests without an account too.
    assert f"View event: http://app.test/event/{token}\n" in message.body
    assert isinstance(message, EmailMultiAlternatives)
    html = str(next(content for content, mimetype in message.alternatives if mimetype == "text/html"))
    assert f'href="http://app.test/event/{token}"' in html and ">Planning</h1>" in html
    # Light or dark, as the reader's system is set (where the mail program follows it).
    assert 'content="light dark"' in html and "prefers-color-scheme: dark" in html
    # Times are shown in the event's zone to guests (09:00 UTC is 10:00 in Berlin in January).
    assert "10:00 AM" in message.body and "(Europe/Berlin)" in message.body


def test_participants_given_with_a_new_event_are_invited(world: World) -> None:
    create(world, participants=[{"email": GUEST}, {"user_id": str(world["users"]["other"].id)}])
    assert len(to(GUEST)) == 1
    assert len(to("other@example.test")) == 1


def test_invitations_name_the_imip_mailbox_as_organizer(world: World, settings: Settings) -> None:
    settings.IMIP_ADDRESS = "meanwhile@app.test"
    invite(world, create(world))
    _, vevent = itip(to(GUEST)[0])
    assert str(vevent["ORGANIZER"]) == "mailto:meanwhile@app.test"
    assert vevent["ORGANIZER"].params["CN"] == "Owner"


def test_users_who_turned_invitations_off_get_them_in_the_app_only(world: World) -> None:
    other = world["users"]["other"]
    other.email_notifications = {"invitations": False}
    other.save()
    invite(world, create(world), other.email)
    assert to(other.email) == []
    assert Notification.objects.filter(user=other, type="participant_added").exists()


def test_emails_are_written_in_the_language_of_the_recipient(world: World) -> None:
    other = world["users"]["other"]
    other.language = "de"
    other.time_format = "24h"
    other.timezone = "Europe/Berlin"
    other.save()
    invite(world, create(world), other.email)
    [message] = to(other.email)
    assert message.subject.startswith("Einladung: Planning @ Mo., 7. Jan. 2030, 10:00")
    assert "Zusagen" in message.body
    # The same words as the invitation page's buttons.
    assert "Vorläufig:" in message.body and "Ablehnen:" in message.body


def test_changes_participants_see_are_sent_as_update_with_a_higher_sequence(world: World) -> None:
    event = create(world)
    invite(world, event)
    owner = world["api"]["owner"]
    owner.patch(
        f"/events/{event['id']}", {"start": iso(BASE + timedelta(hours=2)), "end": iso(BASE + timedelta(hours=3))}
    )
    _, update = to(GUEST)
    assert update.subject.startswith("Updated invitation: Planning")
    method, vevent = itip(update)
    assert method == "REQUEST" and vevent["SEQUENCE"] == 1
    # The category concerns the calendar only.
    category = owner.post(f"/calendars/{world['cal']['id']}/categories", {"name": "Team", "color": "#ff0000"}).json()
    owner.patch(f"/events/{event['id']}", {"category_id": category["id"]})
    assert len(to(GUEST)) == 2


def test_changing_one_occurrence_sends_the_series_with_the_change(world: World) -> None:
    event = create(world, rrule="FREQ=DAILY;COUNT=3")
    invite(world, event)
    second = BASE + timedelta(days=1)
    url = f"/events/{event['id']}/occurrences/{iso(second).replace('+', '%2B')}?scope=this"
    world["api"]["owner"].patch(url, {"title": "Planning (moved)"})
    ical = icalendar.Calendar.from_ical(to(GUEST)[-1].attachments[0][1])
    titles = sorted(str(v["SUMMARY"]) for v in ical.walk("VEVENT"))
    assert titles == ["Planning", "Planning (moved)"]


def test_participants_taken_off_the_event_get_a_cancellation(world: World) -> None:
    event = create(world)
    participant = invite(world, event)
    invite(world, event, "second@elsewhere.test")
    world["api"]["owner"].delete(f"/events/{event['id']}/participants/{participant['id']}")
    method, vevent = itip(to(GUEST)[-1])
    assert method == "CANCEL"
    assert str(vevent["STATUS"]) == "CANCELLED"
    # Only those taken off are named.
    assert str(vevent["ATTENDEE"]) == f"mailto:{GUEST}"
    assert len(to("second@elsewhere.test")) == 1


def test_deleting_or_rejecting_the_event_cancels_it_for_everyone(world: World) -> None:
    event = create(world)
    invite(world, event)
    world["api"]["owner"].delete(f"/events/{event['id']}")
    method, vevent = itip(to(GUEST)[-1])
    assert method == "CANCEL" and vevent["SEQUENCE"] == 1
    assert to(GUEST)[-1].subject.startswith("Cancelled: Planning")

    room = world["resource"]("Room")
    booking = world["book"](world["api"]["booker"], room["id"], participants=[{"email": GUEST}]).json()
    _, vevent = itip(to(GUEST)[-1])
    assert str(vevent["UID"]) == booking["uid"] and str(vevent["STATUS"]) == "TENTATIVE"
    world["api"]["owner"].post(f"/events/{booking['id']}/reject", {})
    assert itip(to(GUEST)[-1])[0] == "CANCEL"


# Answers ---------------------------------------------------------------------------------------


def test_guests_answer_by_link_without_an_account(world: World) -> None:
    event = create(world)
    invite(world, event)
    token = EventParticipant.objects.get(email=GUEST).rsvp_token
    anonymous = Client()
    shown = anonymous.get(f"/api/rsvp/{token}").json()
    assert shown["title"] == "Planning" and shown["status"] == "needs_action" and shown["organizer_name"] == "Owner"
    res = anonymous.post(f"/api/rsvp/{token}", {"status": "accepted"}, content_type="application/json")
    assert res.status_code == 200 and res.json()["status"] == "accepted"
    assert status_of(event) == "accepted"
    # The organizer hears of it, in the app and by email.
    notification = Notification.objects.get(user=world["users"]["owner"], type="participant_replied")
    assert notification.data == {"status": "accepted", "email": GUEST, "name": None}
    [message] = to("owner@example.test")
    assert message.subject == "Accepted: Planning"
    assert GUEST in message.body
    assert anonymous.get("/api/rsvp/not-a-token").status_code == 404


def test_the_invitation_page_shows_who_else_comes_without_their_addresses(world: World) -> None:
    # Anyone with the link sees the page: others appear by their name, guests not at all by address.
    event = create(world)
    invite(world, event)
    invite(world, event, email="other@example.test")
    invite(world, event, email="stranger@example.test")
    token = EventParticipant.objects.get(email=GUEST).rsvp_token
    anonymous = Client()
    res = anonymous.get(f"/api/rsvp/{token}")
    shown = res.json()
    assert shown["organizer_name"] == "Owner" and "organizer_email" not in shown
    assert sorted((p["name"] or "", p["you"]) for p in shown["participants"]) == [
        ("", False),
        ("Other", False),
        (GUEST, True),
    ]
    assert "stranger@example.test" not in res.content.decode()
    assert "owner@example.test" not in res.content.decode()


def test_the_invitation_page_offers_the_event_as_file_without_the_people(world: World) -> None:
    event = create(world)
    invite(world, event)
    invite(world, event, email="stranger@example.test")
    token = EventParticipant.objects.get(email=GUEST).rsvp_token
    anonymous = Client()
    ics = anonymous.get(f"/api/rsvp/{token}/ics")
    assert ics.status_code == 200 and ics["Content-Type"].startswith("text/calendar")
    assert 'filename="invite.ics"' in ics["Content-Disposition"]
    cal = icalendar.Calendar.from_ical(ics.content)
    vevent = cal.walk("VEVENT")[0]
    assert str(vevent["UID"]) == event["uid"] and str(vevent["SUMMARY"]) == "Planning"
    assert "ATTENDEE" not in vevent and "ORGANIZER" not in vevent
    assert b"@example.test" not in ics.content
    assert anonymous.get("/api/rsvp/not-a-token/ics").status_code == 404


def test_cancelled_events_cannot_be_answered_by_link(world: World) -> None:
    event = create(world)
    invite(world, event)
    token = EventParticipant.objects.get(email=GUEST).rsvp_token
    world["api"]["owner"].post(f"/events/{event['id']}/cancel", {})
    anonymous = Client()
    assert anonymous.get(f"/api/rsvp/{token}").json()["cancelled"] is True
    assert (
        anonymous.post(f"/api/rsvp/{token}", {"status": "accepted"}, content_type="application/json").status_code == 409
    )


def test_replies_from_mail_programs_set_the_participants_answer(world: World) -> None:
    event = create(world, rrule="FREQ=DAILY;COUNT=3")
    invite(world, event)
    # The occurrence changed before the answer follows the series' answer.
    second = BASE + timedelta(days=1)
    world["api"]["owner"].patch(
        f"/events/{event['id']}/occurrences/{iso(second).replace('+', '%2B')}?scope=this", {"title": "Moved"}
    )
    assert process_email(reply(GUEST, event["uid"], "TENTATIVE")) == [f"{event['uid']}: {GUEST}: tentative"]
    assert set(EventParticipant.objects.filter(email=GUEST).values_list("status", flat=True)) == {"tentative"}
    assert process_email(reply(GUEST, event["uid"], "TENTATIVE")) == [f"{event['uid']}: {GUEST}: tentative (unchanged)"]


def test_replies_count_only_from_the_participant_themselves(world: World) -> None:
    event = create(world)
    invite(world, event)
    result = process_email(reply(GUEST, event["uid"], "DECLINED", sender="mallory@elsewhere.test"))
    assert result == [f"{event['uid']}: {GUEST}: ignored, sent by mallory@elsewhere.test"]
    assert status_of(event) == "needs_action"
    # SENT-BY is the sender's own claim and doesn't let anyone answer for the participant.
    process_email(
        reply(
            GUEST,
            event["uid"],
            "DECLINED",
            sender="mallory@elsewhere.test",
            **{"SENT-BY": "mailto:mallory@elsewhere.test"},
        )
    )
    assert status_of(event) == "needs_action"
    # Nor does a message without a sender, whatever SENT-BY says.
    anonymous = reply(GUEST, event["uid"], "DECLINED", **{"SENT-BY": "mailto:"}).replace(
        f"From: {GUEST}\n".encode(), b""
    )
    assert b"From:" not in anonymous
    process_email(anonymous)
    assert status_of(event) == "needs_action"


def test_replies_for_unknown_invitations_change_nothing(world: World) -> None:
    event = create(world)
    invite(world, event)
    assert process_email(reply("stranger@elsewhere.test", event["uid"], "ACCEPTED")) == [
        f"{event['uid']}: stranger@elsewhere.test: no such invitation"
    ]
    assert process_email(b"Subject: hello\n\njust text") == ["no iTIP message found"]


def test_refresh_sends_the_event_again(world: World) -> None:
    event = create(world)
    invite(world, event)
    cal = icalendar.Calendar()
    cal.add("method", "REFRESH")
    vevent = icalendar.Event()
    vevent.add("uid", event["uid"])
    vevent.add("attendee", f"mailto:{GUEST}")
    cal.add_component(vevent)
    assert process_itip(cal.to_ical(), GUEST) == [f"{event['uid']}: {GUEST}: sent again"]
    assert len(to(GUEST)) == 2


def test_dev_reply_command_answers_like_a_mail_program(world: World, settings: Settings, tmp_path: Path) -> None:
    settings.IMIP_ADDRESS = "meanwhile@app.test"
    event = create(world)
    invite(world, event)
    out = StringIO()
    call_command("imip_reply", event["id"], GUEST, "declined", "--process", stdout=out)
    assert status_of(event) == "declined"
    call_command("imip_reply", event["id"], GUEST, "accepted", stdout=out)
    sent = to("meanwhile@app.test")[-1]
    assert sent.from_email == GUEST
    assert status_of(event) == "declined"  # only once read from the mailbox
    eml = tmp_path / "reply.eml"
    eml.write_bytes(sent.message().as_bytes())
    call_command("process_imip", str(eml), stdout=out)
    assert status_of(event) == "accepted"


def test_participants_answering_in_the_app_tell_the_organizer(world: World) -> None:
    event = create(world)
    other = world["users"]["other"]
    invite(world, event, other.email)
    world["api"]["other"].patch(f"/events/{event['id']}/participants/me", {"status": "declined"})
    notification = Notification.objects.get(user=world["users"]["owner"], type="participant_replied")
    assert notification.actor_id == other.id
    assert to("owner@example.test")[-1].subject == "Declined: Planning"


# Notifications by email ------------------------------------------------------------------------


def test_notifications_come_by_email_as_each_user_chose(world: World) -> None:
    room = world["resource"]("Room")
    world["book"](world["api"]["booker"], room["id"])
    [message] = to("owner@example.test")
    assert message.subject == "Approval requested: Booking"
    assert "http://app.test/notifications" in message.body

    owner = world["api"]["owner"]
    res = owner.patch("/users/me", {"email_notifications": {"approvals": False}})
    assert res.json()["email_notifications"]["approvals"] is False
    assert res.json()["email_notifications"]["comments"] is True
    world["book"](world["api"]["booker"], room["id"], start=BASE + timedelta(days=1))
    assert len(to("owner@example.test")) == 1
    # The other choices stay as they were.
    owner.patch("/users/me", {"email_notifications": {"reminders": True}})
    assert owner.get("/users/me").json()["email_notifications"]["approvals"] is False


def test_comments_come_by_email_with_their_text(world: World) -> None:
    event = create(world)
    world["api"]["other"].post(f"/events/{event['id']}/comments", {"body": "Bring the slides"})
    [message] = to("owner@example.test")
    assert message.subject == "New comment on Planning"
    assert "Bring the slides" in message.body


def test_email_reminders_are_off_unless_chosen(world: World) -> None:
    from core.services.reminders import deliver_due_reminders

    event = create(world)
    world["api"]["owner"].put(f"/events/{event['id']}/reminders", {"minutes": [15]})
    deliver_due_reminders(now=BASE - timedelta(minutes=10))
    assert to("owner@example.test") == []
    world["api"]["owner"].patch("/users/me", {"email_notifications": {"reminders": True}})
    event = create(world, start=iso(BASE + timedelta(days=1)), end=iso(BASE + timedelta(days=1, hours=1)))
    world["api"]["owner"].put(f"/events/{event['id']}/reminders", {"minutes": [15]})
    deliver_due_reminders(now=BASE + timedelta(days=1) - timedelta(minutes=10))
    [message] = to("owner@example.test")
    assert message.subject == "Reminder: Planning"


def test_answers_reach_caldav_clients(world: World) -> None:
    event = create(world)
    invite(world, event)
    before = Event.objects.get(id=event["id"]).updated_at
    process_email(reply(GUEST, event["uid"], "ACCEPTED"))
    assert Event.objects.get(id=event["id"]).updated_at > before


def test_titles_over_several_lines_make_one_line_subjects() -> None:
    from core.services.mail import one_line, sender

    assert one_line("Team\nmeeting\r\n  today") == "Team meeting today"
    assert "\n" not in sender("Ann\nOther", "App")


PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


def sent_logo(message: EmailMessage) -> tuple[bytes, str] | None:
    """The image the email carries for its HTML part (cid:), and the type of the part around both."""
    for part in message.message().walk():
        if part.get("Content-ID") == "<logo@meanwhile>":
            payload = part.get_payload(decode=True)
            assert isinstance(payload, bytes)
            return payload, part.get_content_type()
    return None


def related_parts(message: EmailMessage) -> list[str]:
    related = next(p for p in message.message().walk() if p.get_content_type() == "multipart/related")
    return [p.get_content_type() for p in related.iter_parts()]


def logo_test_message(uploaded: str) -> EmailMessage:
    from core.models.users import get_or_create_app_settings
    from core.services.mail import build_message

    app_settings = get_or_create_app_settings()
    app_settings.logo_url = uploaded
    app_settings.save()
    return build_message("ann@example.test", "Hello", ["Hi"], "en")


def html_of(message: EmailMessage) -> str:
    assert isinstance(message, EmailMultiAlternatives)
    return str(next(content for content, mimetype in message.alternatives if mimetype == "text/html"))


@pytest.mark.parametrize(
    ("uploaded", "image"),
    [
        # Ours, or one uploaded (a data: URL) in a format mail programs show.
        ("", (Path(__file__).parents[1] / "assets" / "mail-logo.png").read_bytes()),
        (f"data:image/png;base64,{base64.b64encode(PNG).decode()}", PNG),
    ],
)
def test_emails_carry_the_logo_they_show(uploaded: str, image: bytes) -> None:
    # Mail programs show images that come with the email at once, but load linked ones only when asked.
    message = logo_test_message(uploaded)
    assert '<img src="cid:logo@meanwhile"' in html_of(message)
    assert sent_logo(message) == (image, "image/png")
    assert related_parts(message) == ["text/html", "image/png"]


@pytest.mark.parametrize(
    ("uploaded", "shown"),
    [
        ("/media/logo.png", "http://app.test/media/logo.png"),
        ("https://cdn.example.com/logo.png", "https://cdn.example.com/logo.png"),
        # Gmail and Outlook show no SVG, and a big image would weigh down every email: the name alone.
        ("data:image/svg+xml;base64,PHN2Zy8+", None),
        (f"data:image/png;base64,{base64.b64encode(PNG * 6000).decode()}", None),
        ("data:image/png;base64,not base64!", None),
    ],
)
def test_logos_that_cannot_come_along_are_linked_or_left_out(uploaded: str, shown: str | None) -> None:
    message = logo_test_message(uploaded)
    html = html_of(message)
    assert (f'<img src="{shown}"' in html) if shown else ("<img" not in html)
    assert sent_logo(message) is None


def test_invitations_color_the_answers_like_the_invitation_page(world: World) -> None:
    invite(world, create(world))
    html = html_of(to(GUEST)[-1])
    for tone, label in (("accept", "Accept"), ("tentative", "Tentative"), ("decline", "Decline")):
        assert re.search(rf'class="mw-tone mw-tone-{tone}"[^>]*>{label}</a>', html)


def shown_text(html: str) -> str:
    """What the reader sees of the body, as one line."""
    body = html[html.index("<body") :]
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", body)).split())


def test_invitations_look_like_the_events_page(world: World) -> None:
    # Who invites, the title, a leaf of a calendar with the day written out beside it, then the answers.
    invite(world, create(world, rrule="FREQ=WEEKLY", location="Room 1"))
    text_ = shown_text(html_of(to(GUEST)[-1]))
    token = EventParticipant.objects.get(email=GUEST).rsvp_token
    assert "Invitation from Owner Planning" in text_
    assert f"{BASE.strftime('%b').upper()} {BASE.day} " in text_
    assert BASE.strftime("%A, %B ") in text_ and "(Europe/Berlin) Weekly" in text_
    assert "Where Room 1 Organizer Owner <owner@example.test>" in text_
    assert "Your answer Accept Tentative Decline You can also answer in your mail program." in text_
    # The button over the address it was sent to: side by side, a long address would be too wide for phones.
    assert f"View event Invited as {GUEST}" in text_
    assert f'href="http://app.test/event/{token}"' in html_of(to(GUEST)[-1])


def test_cancellations_say_so_on_top_and_strike_the_title_through(world: World) -> None:
    event = create(world)
    invite(world, event)
    world["api"]["owner"].delete(f"/events/{event['id']}")
    html = html_of(to(GUEST)[-1])
    assert shown_text(html).startswith('Meanwhile Owner cancelled "Planning". Cancelled by Owner Planning')
    assert re.search(r"<h1[^>]*line-through[^>]*>Planning</h1>", html)
    assert "Your answer" not in html


@pytest.mark.parametrize(
    ("rrule", "said"),
    [("FREQ=DAILY", "Daily"), ("FREQ=MONTHLY;BYMONTHDAY=5", "Monthly"), ("FREQ=WEEKLY;INTERVAL=2", "Repeats")],
)
def test_invitations_say_how_a_series_repeats(world: World, rrule: str, said: str) -> None:
    invite(world, create(world, rrule=rrule))
    assert f"(Europe/Berlin) {said} " in shown_text(html_of(to(GUEST)[-1]))


@pytest.mark.parametrize(
    ("start", "end", "all_day", "language", "shown"),
    [
        # All-day values are midnight UTC, the end inclusive: the same days in every zone.
        ("2030-01-07T00:00Z", "2030-01-07T00:00Z", True, "de", ("JAN", 7, "Montag, 7. Januar 2030", "All day")),
        (
            "2030-03-30T00:00Z",
            "2030-04-01T00:00Z",
            True,
            "en",
            ("MAR", 30, "Saturday, March 30, 2030 – Monday, April 1, 2030", "All day"),
        ),
        # In the reader's zone; over midnight there, both days are named.
        (
            "2030-01-07T22:00Z",
            "2030-01-08T01:00Z",
            False,
            "de",
            ("JAN", 7, "Mo., 7. Jan. 2030, 23:00 – Di., 8. Jan. 2030, 02:00 (Europe/Berlin)", ""),
        ),
    ],
)
def test_the_time_of_an_invitation_is_written_out(
    start: str, end: str, all_day: bool, language: str, shown: tuple[str, int, str, str]
) -> None:
    from core.services.mail import Reader, when_parts

    when = when_parts(
        datetime.fromisoformat(start),
        datetime.fromisoformat(end),
        all_day,
        Reader(language, "Europe/Berlin", twelve_hour=False),
        "All day",
    )
    assert (when.month, when.day, when.date, when.time) == shown


# Occurrences, addresses and answers in detail -----------------------------------------------------


def occurrence_url(event: dict[str, Any], start: datetime) -> str:
    return f"/events/{event['id']}/occurrences/{iso(start).replace('+', '%2B')}?scope=this"


def test_cancelling_one_occurrence_cancels_only_that_one(world: World) -> None:
    event = create(world, rrule="FREQ=DAILY;COUNT=3")
    invite(world, event)
    second = BASE + timedelta(days=1)
    override = world["api"]["owner"].patch(occurrence_url(event, second), {"title": "Moved"}).json()
    assert world["api"]["owner"].post(f"/events/{override['id']}/cancel").status_code == 200
    method, vevent = itip(to(GUEST)[-1])
    assert method == "CANCEL"
    assert vevent.decoded("RECURRENCE-ID").astimezone(BASE.tzinfo) == second and "RRULE" not in vevent


def test_invitations_go_to_single_email_addresses_only(world: World) -> None:
    event = create(world)
    api = world["api"]["owner"]
    for address in (
        "not-an-email",
        "",
        "Evil <victim@elsewhere.test>",
        "a@x.test, b@x.test",
        "a@x.test\r\nBcc: b@x.test",
        "a" * 300 + "@x.test",
    ):
        assert api.post(f"/events/{event['id']}/participants", {"email": address}).status_code == 422, address
    assert django_mail.outbox == []


def test_nobody_sends_more_than_the_hourly_invitations(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    from core.views import events

    monkeypatch.setattr(events, "MAX_INVITATIONS_PER_HOUR", 2)
    event = create(world)
    api = world["api"]["owner"]
    assert [
        api.post(f"/events/{event['id']}/participants", {"email": f"g{i}@elsewhere.test"}).status_code for i in range(3)
    ] == [200, 200, 429]


def test_who_is_invited_to_one_occurrence_gets_that_one_only(world: World) -> None:
    event = create(world, rrule="FREQ=DAILY;COUNT=3")
    second = BASE + timedelta(days=1)
    override = world["api"]["owner"].patch(occurrence_url(event, second), {"title": "Moved"}).json()
    participant = invite(world, {"id": override["id"]})
    ical = icalendar.Calendar.from_ical(to(GUEST)[-1].attachments[0][1])
    vevents = ical.walk("VEVENT")
    assert len(vevents) == 1 and "RRULE" not in vevents[0] and "RECURRENCE-ID" in vevents[0]
    assert "ORGANIZER" in vevents[0]
    assert "Moved" in to(GUEST)[-1].subject
    # The file on their invitation page has that occurrence only, too.
    token = EventParticipant.objects.get(id=participant["id"]).rsvp_token
    downloaded = icalendar.Calendar.from_ical(Client().get(f"/api/rsvp/{token}/ics").content).walk("VEVENT")
    assert len(downloaded) == 1 and str(downloaded[0]["SUMMARY"]) == "Moved" and "RRULE" not in downloaded[0]

    # Taken off it again, they hear so for that occurrence.
    world["api"]["owner"].delete(f"/events/{override['id']}/participants/{participant['id']}")
    method, vevent = itip(to(GUEST)[-1])
    assert method == "CANCEL" and "RECURRENCE-ID" in vevent


def test_answers_for_one_unchanged_occurrence_count(world: World) -> None:
    event = create(world, rrule="FREQ=DAILY;COUNT=3")
    invite(world, event)
    second = BASE + timedelta(days=1)
    vevent = icalendar.Event()
    vevent.add("uid", event["uid"])
    vevent.add("dtstamp", BASE)
    vevent.add("recurrence-id", second)
    vevent.add("attendee", icalendar.vCalAddress(f"mailto:{GUEST}"), parameters={"PARTSTAT": "DECLINED"})
    ical = icalendar.Calendar()
    ical.add("method", "REPLY")
    ical.add_component(vevent)
    assert process_itip(ical.to_ical(), GUEST) == [f"{event['uid']}: {GUEST}: declined"]
    statuses = dict(EventParticipant.objects.filter(email=GUEST).values_list("event__recurrence_id", "status"))
    assert statuses == {None: "needs_action", second: "declined"}

    # The answer for the series leaves that one alone.
    process_email(reply(GUEST, event["uid"], "ACCEPTED"))
    statuses = dict(EventParticipant.objects.filter(email=GUEST).values_list("event__recurrence_id", "status"))
    assert statuses == {None: "accepted", second: "declined"}


def test_answers_are_asked_again_when_the_event_moves(world: World) -> None:
    event = create(world)
    invite(world, event)
    process_email(reply(GUEST, event["uid"], "ACCEPTED"))
    world["api"]["owner"].patch(
        f"/events/{event['id']}",
        {"start": iso(BASE + timedelta(days=1)), "end": iso(BASE + timedelta(days=1, hours=1))},
    )
    assert status_of(event) == "needs_action"
    _, vevent = itip(to(GUEST)[-1])
    assert vevent["ATTENDEE"].params["PARTSTAT"] == "NEEDS-ACTION"


def test_cancelled_events_take_no_answers_and_are_cancelled_once(world: World) -> None:
    event = create(world)
    invite(world, event)
    world["api"]["owner"].post(f"/events/{event['id']}/cancel")
    assert "cancelled" in process_email(reply(GUEST, event["uid"], "DECLINED"))[0]
    assert status_of(event) == "needs_action"
    cancels = len(to(GUEST))
    world["api"]["owner"].delete(f"/events/{event['id']}")
    assert len(to(GUEST)) == cancels


def test_with_an_authserv_id_answers_need_a_verified_sender(world: World, settings: Settings) -> None:
    settings.IMIP_TRUSTED_AUTHSERV_ID = "mx.example.test"
    event = create(world)
    invite(world, event)
    forged = reply(GUEST, event["uid"], "DECLINED")
    assert process_email(forged)[0].startswith("ignored")
    # Another server's verdict counts for nothing; ours does.
    elsewhere = b"Authentication-Results: mx.attacker.test; dmarc=pass header.from=elsewhere.test\n" + forged
    assert process_email(elsewhere)[0].startswith("ignored")
    verified = b"Authentication-Results: mx.example.test; dkim=pass header.d=elsewhere.test; spf=pass\n" + forged
    assert process_email(verified) == [f"{event['uid']}: {GUEST}: declined"]


def test_updates_say_what_changed_and_show_what_it_was(world: World) -> None:
    event = create(world, location="Room 1")
    invite(world, event)
    world["api"]["owner"].patch(
        f"/events/{event['id']}",
        {"location": "Room 2", "start": iso(BASE + timedelta(hours=2)), "end": iso(BASE + timedelta(hours=3))},
    )
    _, update = to(GUEST)
    html = html_of(update)
    assert "mw-notice-warning" in html
    assert "Owner changed &quot;Planning&quot;." in html
    # The old place and time, struck through under the new ones; the unchanged title isn't.
    before = re.findall(r'<div class="mw-before"[^>]*>([^<]*)</div>', html)
    assert before == ["Mon, Jan 7, 2030, 10:00 AM – 11:00 AM (Europe/Berlin)", "Room 1"]


def test_event_notifications_show_the_event_like_invitations_do(world: World) -> None:
    room = world["resource"]("Beamer")
    world["book"](world["api"]["booker"], room["id"], location="Hall")
    [message] = to("owner@example.test")
    html = html_of(message)
    assert "Booking request" in html and "mw-notice-warning" in html
    # What the approval is about.
    assert ">Resource</td>" in html and "Beamer" in html and "Hall" in html
    assert "Review request" in html

    event = create(world)
    invite(world, event)
    process_email(reply(GUEST, event["uid"], "DECLINED"))
    answer = to("owner@example.test")[-1]
    assert answer.subject == "Declined: Planning"
    assert "mw-notice-danger" in html_of(answer)


def test_new_members_read_what_their_role_allows(world: World) -> None:
    newcomer = world["users"]["outsider"]
    world["api"]["owner"].post(
        f"/calendars/{world['cal']['id']}/members", {"user_id": str(newcomer.id), "role": "full"}
    )
    [message] = to(newcomer.email)
    assert 'Owner added you to the calendar "Team".' in message.body
    assert "Your role: Can create and edit all events" in message.body


def test_role_changes_come_by_email_only_when_chosen_and_for_more_rights(world: World) -> None:
    other = world["users"]["other"]
    url = f"/calendars/{world['cal']['id']}/members/{other.id}"
    owner = world["api"]["owner"]
    assert world["api"]["other"].get("/users/me").json()["email_notifications"]["role_changes"] is False
    owner.patch(url, {"role": "full"})
    assert to(other.email) == []

    world["api"]["other"].patch("/users/me", {"email_notifications": {"role_changes": True}})
    owner.patch(url, {"role": "read"})
    assert to(other.email) == []
    owner.patch(url, {"role": "manage"})
    [message] = to(other.email)
    assert 'Owner changed your rights in the calendar "Team".' in message.body
    assert "Your role: Can create and edit all events, and change settings and access" in message.body
    # In the app, every change is shown.
    assert Notification.objects.filter(user=other, type="member_role_changed").count() == 3
