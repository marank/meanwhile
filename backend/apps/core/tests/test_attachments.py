"""
Attachments: files and links on events, who may add, see and remove them, what files are let in,
the limits, and how they reach CalDAV clients and participants.
"""

from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from pytest_django.fixtures import Settings
from radicale import config
from radicale import item as radicale_item

from apps.core.caldav.storage import Collection, acting_as
from apps.core.models import Calendar, CalendarMember, Event, EventActivity, EventAttachment, FeedToken
from apps.core.services import attachments
from apps.core.services.ical import SCHEDULING, build_series_ical, serialize_event_ical
from apps.core.tests.helpers import BASE, Api, Response, World, iso, make_user

pytestmark = pytest.mark.django_db

HOUR = timedelta(hours=1)
PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj << >> endobj\ntrailer << >>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 20


def create(world: World, user: str = "owner", **fields: Any) -> dict[str, Any]:
    data = {"title": "Meeting", "start": iso(BASE), "end": iso(BASE + HOUR), "timezone": "UTC", **fields}
    res = world["api"][user].post(f"/calendars/{world['cal']['id']}/events", data)
    assert res.status_code == 200, res.content
    event: dict[str, Any] = res.json()
    return event


def upload(api: Api, event_id: str, name: str, content: bytes) -> Response:
    # Multipart, as a browser sends a file.
    response: Response = api.client.post(
        f"/api/events/{event_id}/attachments/files", {"file": SimpleUploadedFile(name, content)}
    )
    return response


def link(api: Api, event_id: str, url: str, name: str = "") -> Response:
    return api.post(f"/events/{event_id}/attachments/links", {"url": url, "name": name})


def listed(api: Api, event_id: str) -> list[dict[str, Any]]:
    res = api.get(f"/events/{event_id}/attachments")
    assert res.status_code == 200, res.content
    found: list[dict[str, Any]] = res.json()
    return found


def detail(res: Response) -> str:
    return str(res.json()["detail"])


@pytest.fixture
def reader(world: World) -> Api:
    """A member who may only look at the calendar."""
    user = make_user("reader")
    CalendarMember.objects.create(calendar_id=world["cal"]["id"], user=user, role="read")
    return Api(user)


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


def test_a_file_is_kept_and_listed(world: World, attachment_dir: Path) -> None:
    event = create(world)
    res = upload(world["api"]["owner"], event["id"], "Agenda.pdf", PDF)
    assert res.status_code == 200, res.content
    added = res.json()
    assert added["kind"] == "file"
    assert added["name"] == "Agenda.pdf"
    assert added["content_type"] == "application/pdf"
    assert added["size"] == len(PDF)
    assert added["url"] == f"/api/attachments/{added['id']}/download"
    assert added["added_by_name"] == "Owner"
    assert listed(world["api"]["owner"], event["id"]) == [added]
    stored = attachments.file_path(EventAttachment.objects.get(id=added["id"]))
    assert stored.read_bytes() == PDF
    assert stored.is_relative_to(attachment_dir)


def test_a_file_is_downloaded_never_shown(world: World) -> None:
    event = create(world)
    added = upload(world["api"]["owner"], event["id"], "Agenda.pdf", PDF).json()
    res = world["api"]["owner"].client.get(added["url"])
    assert res.status_code == 200
    assert res.getvalue() == PDF
    assert res["Content-Type"] == "application/pdf"
    assert res["Content-Disposition"].startswith("attachment;")
    assert 'filename="Agenda.pdf"' in res["Content-Disposition"]
    assert res["X-Content-Type-Options"] == "nosniff"
    assert "sandbox" in res["Content-Security-Policy"]


def test_a_file_gone_from_the_disk_says_so(world: World) -> None:
    # E.g. after the database was restored without the data volume.
    event = create(world)
    added = upload(world["api"]["owner"], event["id"], "Agenda.pdf", PDF).json()
    attachments.file_path(EventAttachment.objects.get(id=added["id"])).unlink()
    res = world["api"]["owner"].client.get(added["url"])
    assert res.status_code == 404
    assert res.json()["detail"] == "The file is no longer there"


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("notes.txt", b"Bring cake\n"),
        ("list.csv", "name;amount\nÄpfel;3\n".encode("cp1252")),
        ("photo.png", PNG),
        ("photo.JPG", b"\xff\xd8\xff\xe0" + b"\x00" * 16),
        ("anim.gif", b"GIF89a" + b"\x00" * 10),
        ("pic.webp", b"RIFF\x24\x00\x00\x00WEBPVP8 "),
        ("letter.docx", b"PK\x03\x04" + b"\x00" * 26),
        ("sheet.ods", b"PK\x03\x04" + b"\x00" * 26),
        ("old.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 8),
        ("text.rtf", b"{\\rtf1\\ansi Hello}"),
        ("invite.ics", b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"),
    ],
)
def test_common_documents_and_images_are_let_in(world: World, name: str, content: bytes) -> None:
    event = create(world)
    res = upload(world["api"]["owner"], event["id"], name, content)
    assert res.status_code == 200, res.content


@pytest.mark.parametrize(
    "name",
    ["page.html", "page.htm", "drawing.svg", "script.js", "setup.exe", "run.sh", "noextension", "archive.tar.gz"],
)
def test_types_a_browser_or_system_would_run_are_refused(world: World, name: str) -> None:
    event = create(world)
    res = upload(world["api"]["owner"], event["id"], name, b"<script>alert(1)</script>")
    assert res.status_code == 415
    assert detail(res) == "Files of this type can't be attached"
    assert not EventAttachment.objects.exists()


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("invoice.pdf", b"<html><script>alert(1)</script></html>"),
        ("photo.png", b"<svg onload=alert(1)>"),
        ("photo.jpg", PNG),
        ("letter.docx", PDF),
        ("notes.txt", b"MZ\x90\x00\x03\x00\x00\x00"),  # a program, by its NUL bytes
    ],
)
def test_content_must_match_the_name(world: World, name: str, content: bytes, attachment_dir: Path) -> None:
    event = create(world)
    res = upload(world["api"]["owner"], event["id"], name, content)
    assert res.status_code == 415
    assert detail(res) == "The file's content doesn't match its type"
    assert not attachment_dir.exists() or not any(attachment_dir.rglob("*"))


def test_empty_files_are_refused(world: World) -> None:
    event = create(world)
    res = upload(world["api"]["owner"], event["id"], "empty.txt", b"")
    assert res.status_code == 422
    assert detail(res) == "The file is empty"


@pytest.mark.parametrize(
    ("uploaded", "kept"),
    [
        ("../../etc/passwd.txt", "passwd.txt"),
        ("C:\\Users\\Anna\\report.pdf", "report.pdf"),
        ("bad\x00na\x1bme.pdf", "badname.pdf"),
        ("  spaced.pdf  ", "spaced.pdf"),
        (f"{'x' * 300}.pdf", f"{'x' * 251}.pdf"),
    ],
)
def test_names_lose_directories_and_control_characters(world: World, uploaded: str, kept: str) -> None:
    assert attachments.clean_name(uploaded) == kept


def test_files_beyond_the_size_limit_are_refused(world: World, settings: Settings) -> None:
    settings.ATTACHMENT_MAX_SIZE = 1024 * 1024
    event = create(world)
    res = upload(world["api"]["owner"], event["id"], "big.txt", b"a" * (1024 * 1024 + 1))
    assert res.status_code == 413
    assert detail(res) == "Files may be at most 1 MB"
    assert upload(world["api"]["owner"], event["id"], "fits.txt", b"a" * (1024 * 1024)).status_code == 200


def test_size_zero_allows_links_only(world: World, settings: Settings) -> None:
    settings.ATTACHMENT_MAX_SIZE = 0
    event = create(world)
    res = upload(world["api"]["owner"], event["id"], "notes.txt", b"hi")
    assert res.status_code == 422
    assert detail(res) == "Files can't be attached here, only links"
    assert link(world["api"]["owner"], event["id"], "https://example.org").status_code == 200


def test_a_calendar_has_room_for_so_many_files(world: World, settings: Settings) -> None:
    settings.ATTACHMENT_CALENDAR_QUOTA = 100
    first, second = create(world), create(world)
    api = world["api"]["owner"]
    assert upload(api, first["id"], "a.txt", b"a" * 60).status_code == 200
    # The files of all the calendar's events count together.
    res = upload(api, second["id"], "b.txt", b"b" * 50)
    assert res.status_code == 413
    assert detail(res) == "There's no room left for files in this calendar"
    assert upload(api, second["id"], "b.txt", b"b" * 40).status_code == 200
    # Links take no room.
    assert link(api, second["id"], "https://example.org").status_code == 200
    # Another calendar has room of its own.
    other = api.post("/calendars", {"name": "Other"}).json()
    elsewhere = api.post(
        f"/calendars/{other['id']}/events", {"title": "x", "start": iso(BASE), "end": iso(BASE + HOUR)}
    ).json()
    assert upload(api, elsewhere["id"], "c.txt", b"c" * 60).status_code == 200


def test_an_event_has_room_for_so_many_attachments(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(attachments, "MAX_PER_EVENT", 2)
    event = create(world)
    api = world["api"]["owner"]
    assert upload(api, event["id"], "a.txt", b"a").status_code == 200
    assert link(api, event["id"], "https://example.org").status_code == 200
    res = upload(api, event["id"], "b.txt", b"b")
    assert res.status_code == 422
    assert detail(res) == "An event can have at most 2 attachments"
    assert link(api, event["id"], "https://example.com").status_code == 422


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


def test_a_link_is_named_by_its_title_or_its_address(world: World) -> None:
    event = create(world)
    api = world["api"]["owner"]
    named = link(api, event["id"], "https://example.org/plan", " The plan ").json()
    bare = link(api, event["id"], "http://example.com/x").json()
    assert (named["kind"], named["name"], named["url"]) == ("link", "The plan", "https://example.org/plan")
    assert (bare["name"], bare["url"]) == ("http://example.com/x", "http://example.com/x")
    assert (named["size"], named["content_type"]) == (0, "")
    assert [a["name"] for a in listed(api, event["id"])] == ["The plan", "http://example.com/x"]


@pytest.mark.parametrize(
    "url",
    ["javascript:alert(1)", "data:text/html,<script>", "file:///etc/passwd", "ftp://example.org/x", "https://", "plan"],
)
def test_only_web_links_are_attached(world: World, url: str) -> None:
    event = create(world)
    assert link(world["api"]["owner"], event["id"], url).status_code == 422


def test_links_are_not_downloads(world: World) -> None:
    event = create(world)
    added = link(world["api"]["owner"], event["id"], "https://example.org").json()
    assert world["api"]["owner"].client.get(f"/api/attachments/{added['id']}/download").status_code == 404


# ---------------------------------------------------------------------------
# Who may do what
# ---------------------------------------------------------------------------


def test_readers_see_and_download_but_change_nothing(world: World, reader: Api) -> None:
    event = create(world)
    added = upload(world["api"]["owner"], event["id"], "Agenda.pdf", PDF).json()
    assert [a["id"] for a in listed(reader, event["id"])] == [added["id"]]
    assert reader.client.get(added["url"]).status_code == 200
    assert upload(reader, event["id"], "mine.txt", b"x").status_code == 403
    assert link(reader, event["id"], "https://example.org").status_code == 403
    assert reader.delete(f"/events/{event['id']}/attachments/{added['id']}").status_code == 403


def test_members_who_add_their_own_events_only_change_those(world: World) -> None:
    owners = create(world)
    theirs = create(world, "booker")
    booker = world["api"]["booker"]
    assert upload(booker, owners["id"], "x.txt", b"x").status_code == 403
    assert upload(booker, theirs["id"], "x.txt", b"x").status_code == 200
    # Who may change every event (full access) changes theirs too.
    assert link(world["api"]["full"], theirs["id"], "https://example.org").status_code == 200


def test_outsiders_learn_nothing(world: World) -> None:
    event = create(world)
    added = upload(world["api"]["owner"], event["id"], "Agenda.pdf", PDF).json()
    outsider = world["api"]["outsider"]
    assert outsider.get(f"/events/{event['id']}/attachments").status_code == 404
    assert outsider.client.get(added["url"]).status_code == 404
    assert upload(outsider, event["id"], "x.txt", b"x").status_code == 404
    assert Client().get(added["url"]).status_code == 401


def test_a_pending_booking_keeps_its_files_to_those_who_see_it(world: World) -> None:
    room = world["resource"]("Room")
    booking = world["book"](world["api"]["booker"], room["id"]).json()
    assert booking["status"] == "pending"
    added = upload(world["api"]["booker"], booking["id"], "plan.pdf", PDF).json()
    assert world["api"]["other"].client.get(added["url"]).status_code == 404
    assert world["api"]["owner"].client.get(added["url"]).status_code == 200  # decides on it


def test_an_attachment_is_removed_from_its_own_event_only(world: World) -> None:
    first, second = create(world), create(world)
    added = link(world["api"]["owner"], first["id"], "https://example.org").json()
    res = world["api"]["owner"].delete(f"/events/{second['id']}/attachments/{added['id']}")
    assert res.status_code == 404
    assert EventAttachment.objects.filter(id=added["id"]).exists()


# ---------------------------------------------------------------------------
# Removing, the activity log, series
# ---------------------------------------------------------------------------


def test_removing_a_file_deletes_it_once_committed(
    world: World, django_capture_on_commit_callbacks: Callable[..., Any]
) -> None:
    event = create(world)
    added = upload(world["api"]["owner"], event["id"], "Agenda.pdf", PDF).json()
    stored = attachments.file_path(EventAttachment.objects.get(id=added["id"]))
    with django_capture_on_commit_callbacks(execute=True):
        res = world["api"]["owner"].delete(f"/events/{event['id']}/attachments/{added['id']}")
    assert res.status_code == 200
    assert not stored.exists()
    assert listed(world["api"]["owner"], event["id"]) == []


def test_deleting_the_event_deletes_its_files(
    world: World, django_capture_on_commit_callbacks: Callable[..., Any]
) -> None:
    event = create(world)
    added = upload(world["api"]["owner"], event["id"], "Agenda.pdf", PDF).json()
    stored = attachments.file_path(EventAttachment.objects.get(id=added["id"]))
    with django_capture_on_commit_callbacks(execute=True):
        world["api"]["owner"].delete(f"/events/{event['id']}")
    assert not stored.exists()


def test_deleting_the_calendar_deletes_its_files(
    world: World, django_capture_on_commit_callbacks: Callable[..., Any]
) -> None:
    event = create(world)
    added = upload(world["api"]["owner"], event["id"], "Agenda.pdf", PDF).json()
    stored = attachments.file_path(EventAttachment.objects.get(id=added["id"]))
    with django_capture_on_commit_callbacks(execute=True):
        Calendar.objects.get(id=world["cal"]["id"]).delete()
    assert not stored.exists()


def test_a_file_whose_record_fails_is_not_left_behind(
    world: World, monkeypatch: pytest.MonkeyPatch, attachment_dir: Path
) -> None:
    event = create(world)

    def broken_save(*args: object, **kwargs: object) -> None:
        raise RuntimeError("database gone")

    monkeypatch.setattr(EventAttachment, "save", broken_save)
    with pytest.raises(RuntimeError, match="database gone"):
        upload(world["api"]["owner"], event["id"], "Agenda.pdf", PDF)
    assert not any(p.is_file() for p in attachment_dir.rglob("*"))


def test_the_activity_log_names_what_was_added_and_removed(world: World) -> None:
    event = create(world)
    api = world["api"]["owner"]
    added = upload(api, event["id"], "Agenda.pdf", PDF).json()
    link(api, event["id"], "https://example.org", "Slides")
    api.delete(f"/events/{event['id']}/attachments/{added['id']}")
    entries = EventActivity.objects.filter(event_id=event["id"], action__startswith="attachment").order_by("created_at")
    assert [(e.action, e.details) for e in entries] == [
        ("attachment_added", {"name": "Agenda.pdf"}),
        ("attachment_added", {"name": "Slides"}),
        ("attachment_removed", {"name": "Agenda.pdf"}),
    ]


def test_adding_counts_as_a_change_for_caldav_clients(world: World) -> None:
    event = create(world)
    before = Event.objects.get(id=event["id"]).updated_at
    link(world["api"]["owner"], event["id"], "https://example.org")
    assert Event.objects.get(id=event["id"]).updated_at > before


def test_every_occurrence_of_a_series_has_the_series_attachments(world: World) -> None:
    series = create(world, rrule="FREQ=DAILY;COUNT=3")
    api = world["api"]["owner"]
    second = iso(BASE + 24 * HOUR).replace("+", "%2B")
    changed = api.patch(f"/events/{series['id']}/occurrences/{second}?scope=this", {"title": "Moved"}).json()
    # Added from the changed occurrence's dialog, it lands on the series.
    added = link(api, changed["id"], "https://example.org").json()
    assert EventAttachment.objects.get(id=added["id"]).event_id == Event.objects.get(id=series["id"]).id
    assert [a["id"] for a in listed(api, series["id"])] == [added["id"]]
    assert [a["id"] for a in listed(api, changed["id"])] == [added["id"]]
    assert api.delete(f"/events/{changed['id']}/attachments/{added['id']}").status_code == 200


# ---------------------------------------------------------------------------
# iCalendar out
# ---------------------------------------------------------------------------


def lines(text: str) -> list[str]:
    return text.replace("\r\n ", "").split("\r\n")


def attach_lines(text: str) -> list[str]:
    return [line for line in lines(text) if line.startswith("ATTACH")]


def test_caldav_clients_get_links_and_where_to_download_files(world: World) -> None:
    event = create(world)
    api = world["api"]["owner"]
    added = upload(api, event["id"], "Agenda.pdf", PDF).json()
    link(api, event["id"], "https://example.org/plan", "The plan")
    link(api, event["id"], "https://example.org/bare")
    text = serialize_event_ical(Event.objects.get(id=event["id"]))
    assert attach_lines(text) == [
        f"ATTACH;FILENAME=Agenda.pdf;FMTTYPE=application/pdf;SIZE={len(PDF)}:http://app.test/api/attachments/{added['id']}/download",
        "ATTACH;FILENAME=The plan:https://example.org/plan",
        "ATTACH:https://example.org/bare",
    ]


def test_participants_invitations_carry_only_the_links(world: World) -> None:
    event = create(world)
    api = world["api"]["owner"]
    upload(api, event["id"], "Agenda.pdf", PDF)
    link(api, event["id"], "https://example.org/plan")
    components = build_series_ical(Event.objects.get(id=event["id"]), SCHEDULING)
    found = components[0].get("ATTACH")
    found = found if isinstance(found, list) else [found]
    assert [str(a) for a in found] == ["https://example.org/plan"]


def test_the_public_feed_has_no_attachments(world: World) -> None:
    event = create(world)
    link(world["api"]["owner"], event["id"], "https://example.org/plan")
    calendar = Calendar.objects.get(id=world["cal"]["id"])
    FeedToken.objects.create(calendar=calendar, user=world["users"]["owner"], token="tok")
    assert "ATTACH" not in Client().get("/ics/tok.ics").content.decode()


def test_changed_occurrences_dont_repeat_the_series_attachments(world: World) -> None:
    series = create(world, rrule="FREQ=DAILY;COUNT=3")
    api = world["api"]["owner"]
    link(api, series["id"], "https://example.org/plan")
    second = iso(BASE + 24 * HOUR).replace("+", "%2B")
    api.patch(f"/events/{series['id']}/occurrences/{second}?scope=this", {"title": "Moved"})
    assert attach_lines(serialize_event_ical(Event.objects.get(id=series["id"]))) == ["ATTACH:https://example.org/plan"]


# ---------------------------------------------------------------------------
# CalDAV in
# ---------------------------------------------------------------------------


def ics(uid: str, attach: str = "", start: datetime = BASE) -> str:
    fmt = "%Y%m%dT%H%M%SZ"
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\nDTSTAMP:{start.strftime(fmt)}\r\n"
        f"DTSTART:{start.strftime(fmt)}\r\nDTEND:{(start + HOUR).strftime(fmt)}\r\n"
        f"SUMMARY:From a client\r\n{attach}"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )


@pytest.fixture
def as_owner(world: World) -> Iterator[None]:
    with acting_as(world["users"]["owner"].email):
        yield


def put(world: World, uid: str, text: str) -> Event:
    calendar = Calendar.objects.get(id=world["cal"]["id"])
    owner = world["users"]["owner"]
    coll = Collection(config.load(), f"/{owner.email}/{calendar.id}/", calendar=calendar, user=owner)
    coll.upload(f"{uid}.ics", radicale_item.Item(collection=coll, text=text))
    return Event.objects.get(calendar=calendar, uid=uid, parent__isnull=True)


def links_of(event: Event) -> list[tuple[str, str]]:
    return [(a.url, a.name) for a in event.attachments.filter(kind="link")]


@pytest.mark.usefixtures("as_owner")
def test_links_a_client_attaches_become_attachments(world: World) -> None:
    event = put(
        world,
        "c1",
        ics(
            "c1",
            "ATTACH;FILENAME=Plan.pdf:https://example.org/plan.pdf\r\n"
            "ATTACH;X-APPLE-FILENAME=Notes:https://example.org/notes\r\n"
            "ATTACH:https://example.org/bare\r\n"
            "ATTACH:https://example.org/bare\r\n"  # twice, kept once
            "ATTACH:mailto:someone@example.org\r\n"  # not a web link
            "ATTACH;FMTTYPE=text/plain:cid:part1@example.org\r\n",
        ),
    )
    assert links_of(event) == [
        ("https://example.org/plan.pdf", "Plan.pdf"),
        ("https://example.org/notes", "Notes"),
        ("https://example.org/bare", "https://example.org/bare"),
    ]
    # Served back once each, as the app's own.
    assert len(attach_lines(serialize_event_ical(event))) == 3


@pytest.mark.usefixtures("as_owner")
def test_a_client_removing_a_link_removes_it_but_not_the_files(world: World) -> None:
    event = put(world, "c2", ics("c2", "ATTACH:https://example.org/a\r\nATTACH:https://example.org/b\r\n"))
    added = upload(world["api"]["owner"], str(event.id), "Agenda.pdf", PDF).json()
    # The client sends back what it was served, less one link.
    served = [line for line in attach_lines(serialize_event_ical(event)) if "example.org/a" not in line]
    event = put(world, "c2", ics("c2", "".join(f"{line}\r\n" for line in served)))
    assert links_of(event) == [("https://example.org/b", "https://example.org/b")]
    assert event.attachments.filter(id=added["id"]).exists()
    # A client that drops the file's line doesn't delete the file either.
    event = put(world, "c2", ics("c2", "ATTACH:https://example.org/b\r\n"))
    assert event.attachments.filter(id=added["id"]).exists()
    actions = EventActivity.objects.filter(event=event, action="attachment_removed").values_list("details", flat=True)
    assert list(actions) == [{"name": "https://example.org/a"}]


@pytest.mark.usefixtures("as_owner")
def test_files_a_client_sends_inline_stay_as_they_were(world: World) -> None:
    inline = "ATTACH;ENCODING=BASE64;VALUE=BINARY;FMTTYPE=text/plain;X-FILENAME=a.txt:SGVsbG8=\r\n"
    event = put(world, "c3", ics("c3", inline + "ATTACH:https://example.org/x\r\n"))
    assert links_of(event) == [("https://example.org/x", "https://example.org/x")]
    served = attach_lines(serialize_event_ical(event))
    assert "ATTACH:https://example.org/x" in served
    assert any(line.endswith(":SGVsbG8=") for line in served)
    assert len(served) == 2


@pytest.mark.usefixtures("as_owner")
def test_a_client_adds_no_more_links_than_an_event_has_room_for(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(attachments, "MAX_PER_EVENT", 2)
    event = put(world, "c4", ics("c4", "".join(f"ATTACH:https://example.org/{i}\r\n" for i in range(4))))
    assert [url for url, _ in links_of(event)] == ["https://example.org/0", "https://example.org/1"]


def test_download_urls_are_recognised_on_every_address() -> None:
    assert attachments.is_download_url(
        "https://cal.example.org/api/attachments/0190a1b2c3d4e5f60718293a4b5c6d7e/download"
    )
    assert attachments.is_download_url(
        "http://localhost:6326/api/attachments/0190a1b2-c3d4-e5f6-0718-293a4b5c6d7e/download"
    )
    assert not attachments.is_download_url("https://example.org/api/attachments/x/download")
    assert not attachments.is_download_url("https://example.org/plan.pdf")
