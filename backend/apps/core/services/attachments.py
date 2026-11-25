"""
Files and links attached to events: what may be attached, where files are kept, and copies.

Attachments hang on the series (or the single event), so every occurrence has them. Files are checked
by their name's extension and their first bytes (a PDF must start like one), so that nothing is kept
under a harmless name that a browser would run; they're always served as downloads.
"""

import re
import shutil
import tempfile
import unicodedata
from collections.abc import Callable
from pathlib import Path, PurePath
from typing import IO
from urllib.parse import urlsplit

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext
from ninja.errors import HttpError

from apps.core.models import AttachmentKind, Calendar, Event, EventAttachment, User
from apps.core.realtime import broadcast
from apps.core.services.activity import record_activity

# More would make the event's iCalendar object (every attachment is a line in it) and its dialog unwieldy.
MAX_PER_EVENT = 20

# Bytes read to tell a file's type.
_HEAD = 8192


def _starts(*signatures: bytes) -> Callable[[bytes], bool]:
    return lambda head: head.startswith(signatures)


def _is_text(head: bytes) -> bool:
    # Plain text in whatever encoding; binary files have NUL bytes early on.
    return b"\0" not in head


def _is_webp(head: bytes) -> bool:
    return head[:4] == b"RIFF" and head[8:12] == b"WEBP"


_ZIP = _starts(b"PK\x03\x04", b"PK\x05\x06")
_OLE = _starts(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")  # the old Office formats
_OOXML = "application/vnd.openxmlformats-officedocument"
_ODF = "application/vnd.oasis.opendocument"

# What may be attached, by extension: the type it's served as, and how its first bytes must look.
FILE_TYPES: dict[str, tuple[str, Callable[[bytes], bool]]] = {
    ".pdf": ("application/pdf", _starts(b"%PDF-")),
    ".png": ("image/png", _starts(b"\x89PNG\r\n\x1a\n")),
    ".jpg": ("image/jpeg", _starts(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", _starts(b"\xff\xd8\xff")),
    ".gif": ("image/gif", _starts(b"GIF87a", b"GIF89a")),
    ".webp": ("image/webp", _is_webp),
    ".txt": ("text/plain", _is_text),
    ".md": ("text/markdown", _is_text),
    ".csv": ("text/csv", _is_text),
    ".ics": ("text/calendar", _is_text),
    ".vcf": ("text/vcard", _is_text),
    ".rtf": ("application/rtf", _starts(b"{\\rtf")),
    ".docx": (f"{_OOXML}.wordprocessingml.document", _ZIP),
    ".xlsx": (f"{_OOXML}.spreadsheetml.sheet", _ZIP),
    ".pptx": (f"{_OOXML}.presentationml.presentation", _ZIP),
    ".odt": (f"{_ODF}.text", _ZIP),
    ".ods": (f"{_ODF}.spreadsheet", _ZIP),
    ".odp": (f"{_ODF}.presentation", _ZIP),
    ".doc": ("application/msword", _OLE),
    ".xls": ("application/vnd.ms-excel", _OLE),
    ".ppt": ("application/vnd.ms-powerpoint", _OLE),
    ".zip": ("application/zip", _ZIP),
}


def series_of(event: Event) -> Event:
    return event.parent or event


# Where the app serves a file attachment; links to it (in CalDAV, from clients) are recognized by it.
_DOWNLOAD = re.compile(r"/api/attachments/[0-9a-fA-F-]{32,36}/download/?")


def download_path(attachment: EventAttachment) -> str:
    return f"/api/attachments/{attachment.id}/download"


def is_download_url(url: str) -> bool:
    """Whether `url` is where the app serves a file attachment (on any of its addresses)."""
    return bool(_DOWNLOAD.fullmatch(urlsplit(url).path))


def file_path(attachment: EventAttachment) -> Path:
    """Where a file attachment's content is kept: by its id, spread over 256 directories."""
    name = attachment.id.hex
    return Path(settings.ATTACHMENT_DIR) / name[-2:] / name


def attachments_of(event: Event) -> list[EventAttachment]:
    return list(series_of(event).attachments.select_related("added_by").order_by("created_at"))


def clean_name(name: str) -> str:
    """A file name as it may be shown and offered for download: without directories and control characters."""
    base = PurePath(name.replace("\\", "/")).name
    base = "".join(c for c in base if unicodedata.category(c)[0] != "C").strip().strip(".")
    if len(base) > 255:
        stem, dot, ext = base.rpartition(".")
        base = f"{stem[: 254 - len(ext)]}.{ext}" if dot and len(ext) < 20 else base[:255]
    return base


def _file_type(name: str, head: bytes) -> str:
    """The content type a file is served as; refuses types that may not be attached and files whose
    content doesn't match their name."""
    known = FILE_TYPES.get(PurePath(name).suffix.lower())
    if known is None:
        raise HttpError(415, gettext("Files of this type can't be attached"))
    content_type, matches = known
    if not matches(head):
        raise HttpError(415, gettext("The file's content doesn't match its type"))
    return content_type


def _check_room(series: Event, count: int = 1, size: int = 0) -> None:
    """Refuses `count` more attachments of `size` bytes in all that don't fit the event or its calendar."""
    if series.attachments.count() + count > MAX_PER_EVENT:
        raise HttpError(422, gettext("An event can have at most %(count)d attachments") % {"count": MAX_PER_EVENT})
    if size and calendar_usage(series.calendar) + size > settings.ATTACHMENT_CALENDAR_QUOTA:
        raise HttpError(413, gettext("There's no room left for files in this calendar"))


def calendar_usage(calendar: Calendar) -> int:
    """Bytes taken by the files of the calendar's events."""
    used = EventAttachment.objects.filter(event__calendar=calendar, kind=AttachmentKind.FILE).aggregate(
        total=Sum("size")
    )["total"]
    return int(used or 0)


def _store(attachment: EventAttachment, source: IO[bytes] | Path) -> None:
    """Writes the file's content, under a temporary name first, so a file is never seen half-written."""
    target = file_path(attachment)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as tmp:
        if isinstance(source, Path):
            with source.open("rb") as src:
                shutil.copyfileobj(src, tmp)
        else:
            shutil.copyfileobj(source, tmp)
    Path(tmp.name).replace(target)


def _save_with_file(attachment: EventAttachment, source: IO[bytes] | Path) -> None:
    """Writes the content, then the record; without the record, the content goes again."""
    _store(attachment, source)
    try:
        attachment.save()
    except BaseException:
        file_path(attachment).unlink(missing_ok=True)
        raise


def delete_file_later(attachment: EventAttachment) -> None:
    """Deletes a file attachment's content once its deletion is committed."""
    if attachment.kind != AttachmentKind.FILE:
        return
    path = file_path(attachment)
    transaction.on_commit(lambda: path.unlink(missing_ok=True))


def _touch(series: Event) -> None:
    # Attachments are part of the event's iCalendar object (ATTACH): CalDAV clients sync it again.
    Event.objects.filter(pk=series.pk).update(updated_at=timezone.now())
    broadcast.calendar_changed(series.calendar_id)


def add_file(event: Event, user: User, upload: UploadedFile[bytes]) -> EventAttachment:
    series = series_of(event)
    name = clean_name(upload.name or "")
    if settings.ATTACHMENT_MAX_SIZE <= 0:
        raise HttpError(422, gettext("Files can't be attached here, only links"))
    if not name:
        raise HttpError(422, gettext("The file needs a name"))
    size = upload.size or 0
    if size == 0:
        raise HttpError(422, gettext("The file is empty"))
    if size > settings.ATTACHMENT_MAX_SIZE:
        raise HttpError(
            413,
            gettext("Files may be at most %(size)d MB") % {"size": settings.ATTACHMENT_MAX_SIZE // (1024 * 1024)},
        )
    upload.seek(0)
    content_type = _file_type(name, upload.read(_HEAD))
    upload.seek(0)
    _check_room(series, size=size)
    attachment = EventAttachment(
        event=series, kind=AttachmentKind.FILE, name=name, content_type=content_type, size=size, added_by=user
    )
    _save_with_file(attachment, upload)
    _added(series, user, attachment)
    return attachment


def add_link(event: Event, user: User, url: str, name: str = "") -> EventAttachment:
    series = series_of(event)
    _check_room(series)
    attachment = EventAttachment.objects.create(
        event=series, kind=AttachmentKind.LINK, name=(name.strip() or url)[:255], url=url, added_by=user
    )
    _added(series, user, attachment)
    return attachment


def _added(series: Event, user: User, attachment: EventAttachment) -> None:
    record_activity(series, str(user.id), "attachment_added", {"name": attachment.name})
    _touch(series)


def sync_links(series: Event, user: User, links: list[tuple[str, str]]) -> None:
    """Makes the event's links those a CalDAV client sent (address, name): new ones are added (as far as
    there is room), missing ones removed. Files stay as they are: clients don't change them."""
    current = {a.url: a for a in series.attachments.filter(kind=AttachmentKind.LINK)}
    wanted = dict(links)
    for url, stale in current.items():
        if url not in wanted:
            stale.delete()
            record_activity(series, str(user.id), "attachment_removed", {"name": stale.name})
    room = MAX_PER_EVENT - series.attachments.count()
    for url, name in wanted.items():
        if url in current:
            continue
        if room <= 0:
            break
        attachment = EventAttachment.objects.create(
            event=series, kind=AttachmentKind.LINK, name=(name or url)[:255], url=url, added_by=user
        )
        record_activity(series, str(user.id), "attachment_added", {"name": attachment.name})
        room -= 1


def remove(attachment: EventAttachment, user: User) -> None:
    series = attachment.event
    name = attachment.name
    attachment.delete()  # the file goes with it (apps.core.signals)
    record_activity(series, str(user.id), "attachment_removed", {"name": name})
    _touch(series)


def copy_attachments(source: Event, target: Event, user: User) -> None:
    """Gives `target` copies of the attachments of `source` (files as files of their own)."""
    originals = attachments_of(source)
    if not originals:
        return
    target = series_of(target)
    size = sum(a.size for a in originals if a.kind == AttachmentKind.FILE)
    _check_room(target, count=len(originals), size=size)
    for original in originals:
        copy = EventAttachment(
            event=target,
            kind=original.kind,
            name=original.name,
            url=original.url,
            content_type=original.content_type,
            size=original.size,
            added_by=user,
        )
        if original.kind == AttachmentKind.LINK:
            copy.save()
        elif file_path(original).is_file():
            _save_with_file(copy, file_path(original))
        # A file whose content is gone (e.g. the data volume was restored from an older backup) isn't copied.
    _touch(target)
