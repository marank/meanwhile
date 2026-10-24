"""
Emails: notifications by email, and scheduling by email (iMIP): invitations, their changes and
cancellations, and the participants' answers by link or from their mail programs.
"""

from datetime import timedelta
from io import StringIO

import icalendar
import pytest
from django.core import mail as django_mail
from django.core.mail import EmailMessage
from django.core.management import call_command
from django.test import Client

from core.models import Event, EventParticipant, Notification
from core.services.itip import process_email, process_itip
from core.tests.helpers import BASE, iso

pytestmark = pytest.mark.django_db

GUEST = "guest@elsewhere.test"


@pytest.fixture(autouse=True)
def empty_outbox(world):
    """Without the emails of setting the calendar up (members are told they were added)."""
    django_mail.outbox.clear()


def create(world, user="owner", **fields):
    data = {"title": "Planning", "start": iso(BASE), "end": iso(BASE + timedelta(hours=1)), "timezone": "Europe/Berlin", **fields}
    res = world["api"][user].post(f"/calendars/{world['cal']['id']}/events", data)
    assert res.status_code == 200, res.content
    return res.json()


def invite(world, event, email=GUEST, user="owner"):
    res = world["api"][user].post(f"/events/{event['id']}/participants", {"email": email})
    assert res.status_code == 200, res.content
    return res.json()


def to(address):
    return [m for m in django_mail.outbox if m.to == [address]]


def itip(message):
    """The METHOD and the VEVENT of the iTIP message an email carries inline."""
    ical = next(content for content, mimetype in message.alternatives if mimetype.startswith("text/calendar"))
    cal = icalendar.Calendar.from_ical(ical)
    return str(cal["METHOD"]), cal.walk("VEVENT")[0]


def reply(participant_email, uid, partstat, sender=None, organizer="owner@example.test", **extra):
    vevent = icalendar.Event()
    vevent.add("uid", uid)
    vevent.add("dtstamp", BASE)
    vevent.add("organizer", f"mailto:{organizer}")
    vevent.add("attendee", icalendar.vCalAddress(f"mailto:{participant_email}"), parameters={"PARTSTAT": partstat, **extra})
    cal = icalendar.Calendar()
    cal.add("prodid", "-//Test//EN")
    cal.add("version", "2.0")
    cal.add("method", "REPLY")
    cal.add_component(vevent)
    message = EmailMessage("Accepted", "", sender or participant_email, [organizer])
    message.attach("invite.ics", cal.to_ical().decode(), "text/calendar; method=REPLY")
    return message.message().as_bytes()


def status_of(event, email=GUEST):
    return EventParticipant.objects.get(event_id=event["id"], email=email).status


# Invitations -----------------------------------------------------------------------------------


def test_invited_guests_get_the_event_as_request_with_links_to_answer(world):
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
    assert f"http://app.test/rsvp/{token}?answer=accepted" in message.body
    # Times are shown in the event's zone to guests (09:00 UTC is 10:00 in Berlin in January).
    assert "10:00 AM" in message.body and "(Europe/Berlin)" in message.body


def test_participants_given_with_a_new_event_are_invited(world):
    create(world, participants=[{"email": GUEST}, {"user_id": str(world["users"]["other"].id)}])
    assert len(to(GUEST)) == 1
    assert len(to("other@example.test")) == 1


def test_invitations_name_the_imip_mailbox_as_organizer(world, settings):
    settings.IMIP_ADDRESS = "meanwhile@app.test"
    invite(world, create(world))
    _, vevent = itip(to(GUEST)[0])
    assert str(vevent["ORGANIZER"]) == "mailto:meanwhile@app.test"
    assert vevent["ORGANIZER"].params["CN"] == "Owner"


def test_users_who_turned_invitations_off_get_them_in_the_app_only(world):
    other = world["users"]["other"]
    other.email_notifications = {"invitations": False}
    other.save()
    invite(world, create(world), other.email)
    assert to(other.email) == []
    assert Notification.objects.filter(user=other, type="participant_added").exists()


def test_emails_are_written_in_the_language_of_the_recipient(world):
    other = world["users"]["other"]
    other.language = "de"
    other.time_format = "24h"
    other.timezone = "Europe/Berlin"
    other.save()
    invite(world, create(world), other.email)
    [message] = to(other.email)
    assert message.subject.startswith("Einladung: Planning @ Mo., 7. Jan. 2030, 10:00")
    assert "Zusagen" in message.body


def test_changes_participants_see_are_sent_as_update_with_a_higher_sequence(world):
    event = create(world)
    invite(world, event)
    owner = world["api"]["owner"]
    owner.patch(f"/events/{event['id']}", {"start": iso(BASE + timedelta(hours=2)), "end": iso(BASE + timedelta(hours=3))})
    _, update = to(GUEST)
    assert update.subject.startswith("Updated invitation: Planning")
    method, vevent = itip(update)
    assert method == "REQUEST" and vevent["SEQUENCE"] == 1
    # The category concerns the calendar only.
    category = owner.post(f"/calendars/{world['cal']['id']}/categories", {"name": "Team", "color": "#ff0000"}).json()
    owner.patch(f"/events/{event['id']}", {"category_id": category["id"]})
    assert len(to(GUEST)) == 2


def test_changing_one_occurrence_sends_the_series_with_the_change(world):
    event = create(world, rrule="FREQ=DAILY;COUNT=3")
    invite(world, event)
    second = BASE + timedelta(days=1)
    url = f"/events/{event['id']}/occurrences/{iso(second).replace('+', '%2B')}?scope=this"
    world["api"]["owner"].patch(url, {"title": "Planning (moved)"})
    ical = icalendar.Calendar.from_ical(to(GUEST)[-1].attachments[0][1])
    titles = sorted(str(v["SUMMARY"]) for v in ical.walk("VEVENT"))
    assert titles == ["Planning", "Planning (moved)"]


def test_participants_taken_off_the_event_get_a_cancellation(world):
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


def test_deleting_or_rejecting_the_event_cancels_it_for_everyone(world):
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


def test_guests_answer_by_link_without_an_account(world):
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


def test_cancelled_events_cannot_be_answered_by_link(world):
    event = create(world)
    invite(world, event)
    token = EventParticipant.objects.get(email=GUEST).rsvp_token
    world["api"]["owner"].post(f"/events/{event['id']}/cancel", {})
    anonymous = Client()
    assert anonymous.get(f"/api/rsvp/{token}").json()["cancelled"] is True
    assert anonymous.post(f"/api/rsvp/{token}", {"status": "accepted"}, content_type="application/json").status_code == 409


def test_replies_from_mail_programs_set_the_participants_answer(world):
    event = create(world, rrule="FREQ=DAILY;COUNT=3")
    invite(world, event)
    # The occurrence changed before the answer follows the series' answer.
    second = BASE + timedelta(days=1)
    world["api"]["owner"].patch(f"/events/{event['id']}/occurrences/{iso(second).replace('+', '%2B')}?scope=this", {"title": "Moved"})
    assert process_email(reply(GUEST, event["uid"], "TENTATIVE")) == [f"{event['uid']}: {GUEST}: tentative"]
    assert set(EventParticipant.objects.filter(email=GUEST).values_list("status", flat=True)) == {"tentative"}
    assert process_email(reply(GUEST, event["uid"], "TENTATIVE")) == [f"{event['uid']}: {GUEST}: tentative (unchanged)"]


def test_replies_count_only_from_the_participant_themselves(world):
    event = create(world)
    invite(world, event)
    result = process_email(reply(GUEST, event["uid"], "DECLINED", sender="mallory@elsewhere.test"))
    assert result == [f"{event['uid']}: {GUEST}: ignored, sent by mallory@elsewhere.test"]
    assert status_of(event) == "needs_action"
    # SENT-BY is the sender's own claim and doesn't let anyone answer for the participant.
    process_email(reply(GUEST, event["uid"], "DECLINED", sender="mallory@elsewhere.test", **{"SENT-BY": "mailto:mallory@elsewhere.test"}))
    assert status_of(event) == "needs_action"
    # Nor does a message without a sender, whatever SENT-BY says.
    anonymous = reply(GUEST, event["uid"], "DECLINED", **{"SENT-BY": "mailto:"}).replace(f"From: {GUEST}\n".encode(), b"")
    assert b"From:" not in anonymous
    process_email(anonymous)
    assert status_of(event) == "needs_action"


def test_replies_for_unknown_invitations_change_nothing(world):
    event = create(world)
    invite(world, event)
    assert process_email(reply("stranger@elsewhere.test", event["uid"], "ACCEPTED")) == [
        f"{event['uid']}: stranger@elsewhere.test: no such invitation"
    ]
    assert process_email(b"Subject: hello\n\njust text") == ["no iTIP message found"]


def test_refresh_sends_the_event_again(world):
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


def test_dev_reply_command_answers_like_a_mail_program(world, settings, tmp_path):
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


def test_participants_answering_in_the_app_tell_the_organizer(world):
    event = create(world)
    other = world["users"]["other"]
    invite(world, event, other.email)
    world["api"]["other"].patch(f"/events/{event['id']}/participants/me", {"status": "declined"})
    notification = Notification.objects.get(user=world["users"]["owner"], type="participant_replied")
    assert notification.actor_id == other.id
    assert to("owner@example.test")[-1].subject == "Declined: Planning"


# Notifications by email ------------------------------------------------------------------------


def test_notifications_come_by_email_as_each_user_chose(world):
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


def test_comments_come_by_email_with_their_text(world):
    event = create(world)
    world["api"]["other"].post(f"/events/{event['id']}/comments", {"body": "Bring the slides"})
    [message] = to("owner@example.test")
    assert message.subject == "New comment on Planning"
    assert "Bring the slides" in message.body


def test_email_reminders_are_off_unless_chosen(world):
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


def test_answers_reach_caldav_clients(world):
    event = create(world)
    invite(world, event)
    before = Event.objects.get(id=event["id"]).updated_at
    process_email(reply(GUEST, event["uid"], "ACCEPTED"))
    assert Event.objects.get(id=event["id"]).updated_at > before


def test_titles_over_several_lines_make_one_line_subjects():
    from core.services.mail import one_line, sender

    assert one_line("Team\nmeeting\r\n  today") == "Team meeting today"
    assert "\n" not in sender("Ann\nOther", "App")
