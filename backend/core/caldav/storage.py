"""
Radicale storage plugin backed by the Django ORM.
"""

import contextlib
import errno
import hashlib
from datetime import date, datetime, timezone

import vobject
from django.db import connection
from email.utils import format_datetime
from radicale import item as radicale_item
from radicale import pathutils, storage

from core.models import Calendar, Event, User
from core.models.base import EventStatus
from core.services.bookings import find_conflicting_approved_bookings
from core.services.ical import event_ical_text
from core.services.recurrence import zone

# CalDAV only knows the calendar, not who is asking, so it shares what everyone may see,
# like the ICS feed: pending, rejected and cancelled bookings stay out.
_SHARED_STATUSES = {EventStatus.CONFIRMED, EventStatus.APPROVED}


def _forbidden(message: str) -> ValueError:
    # Radicale answers a ValueError carrying EACCES with 403 Forbidden.
    return ValueError(f"[Errno {errno.EACCES}] {message}")


def _http_datetime(dt: datetime | None) -> str:
    if dt is None:
        return format_datetime(datetime.now(timezone.utc))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt)


def _to_utc(dt: datetime | date) -> datetime:
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)


def _parse_vevent_data(text: str):
    try:
        vcal = vobject.readOne(text)
    except Exception as exc:
        raise RuntimeError("Failed to parse iCalendar object") from exc

    vevent = vcal
    if hasattr(vcal, "vevent"):
        vevent = vcal.vevent

    summary = ""
    if hasattr(vevent, "summary"):
        summary = str(vevent.summary.value)

    description = None
    if hasattr(vevent, "description"):
        description = str(vevent.description.value)

    dtstart = vevent.dtstart.value if hasattr(vevent, "dtstart") else None
    dtend = vevent.dtend.value if hasattr(vevent, "dtend") else None
    if dtend is None and dtstart is not None:
        dtend = dtstart

    all_day = isinstance(dtstart, date) and not isinstance(dtstart, datetime)
    start = _to_utc(dtstart) if dtstart else datetime.now(timezone.utc)
    end = _to_utc(dtend) if dtend else start

    rrule = None
    if hasattr(vevent, "rrule"):
        rrule = str(vevent.rrule.value)

    # The zone the client planned the event in, so its recurrences repeat in local time.
    event_timezone = "UTC"
    if not all_day and hasattr(vevent, "dtstart"):
        params = vevent.dtstart.params
        # vobject moves the TZID parameter aside when it resolves the zone.
        tzid = (params.get("X-VOBJ-ORIGINAL-TZID") or params.get("TZID") or [None])[0]
        tzid = tzid or getattr(getattr(dtstart, "tzinfo", None), "zone", None)
        if tzid and zone(tzid) is not timezone.utc:
            event_timezone = tzid

    uid = None
    if hasattr(vevent, "uid"):
        uid = str(vevent.uid.value)

    return {
        "title": summary,
        "description": description,
        "start": start,
        "end": end,
        "all_day": all_day,
        "timezone": event_timezone,
        "rrule": rrule,
        "uid": uid,
    }, text


class Collection(storage.BaseCollection):
    def __init__(
        self,
        configuration,
        path: str,
        calendar: Calendar | None = None,
        user: User | None = None,
        is_principal: bool = False,
    ) -> None:
        self.configuration = configuration
        self._path = pathutils.strip_path(path) if path else ""
        self._calendar = calendar
        self._user = user
        self._is_principal = is_principal

    @property
    def path(self) -> str:
        return self._path

    @property
    def is_principal(self) -> bool:
        return self._is_principal or (bool(self.path) and "/" not in self.path)

    def _etag_text(self) -> str:
        parts = []
        for item in self.get_all():
            parts.append(f"{item.href}/{item.etag}")
        parts.append(str(self.get_meta()))
        return "\n".join(parts)

    @property
    def etag(self) -> str:
        data = self._etag_text()
        return f'"{hashlib.sha256(data.encode()).hexdigest()}"'

    def get_meta(self, key: str | None = None):
        meta = {}
        if not self.path:
            meta = {"tag": ""}
        elif self._is_principal or self.is_principal:
            meta = {
                "tag": "",
                "D:displayname": self._user.display_name if self._user else "",
            }
        elif self._calendar:
            meta = {
                "tag": "VCALENDAR",
                "D:displayname": self._calendar.name,
                "C:calendar-description": self._calendar.description or "",
                "C:supported-calendar-component-set": "VEVENT",
            }
        if key is None:
            return meta
        return meta.get(key)

    def set_meta(self, props: dict[str, str]) -> None:
        if self._calendar is None:
            return
        name = props.get("D:displayname")
        if name:
            self._calendar.name = name
        description = props.get("C:calendar-description")
        if description is not None:
            self._calendar.description = description
        self._calendar.save()

    @property
    def last_modified(self) -> str:
        if self._calendar:
            return _http_datetime(self._calendar.updated_at)
        return _http_datetime(datetime.now(timezone.utc))

    def sync(self, old_token: str = ""):
        token = f"http://radicale.org/ns/sync/{self.etag.strip(chr(34))}"
        if old_token == token:
            return token, []
        return token, [item.href for item in self.get_all()]

    def get_all(self):
        if self._calendar is None:
            return []
        events = Event.objects.filter(calendar=self._calendar, status__in=_SHARED_STATUSES)
        for event in events:
            text = event_ical_text(event)
            href = f"{event.uid}.ics"
            last_modified = _http_datetime(event.updated_at)
            yield radicale_item.Item(
                text=text,
                href=href,
                last_modified=last_modified,
                collection=self,
            )

    def get_multi(self, hrefs):
        if self._calendar is None:
            for href in hrefs:
                yield href, None
            return
        requested = {h.strip("/") for h in hrefs}
        uid_set = {h[:-4] if h.endswith(".ics") else h for h in requested}
        events = Event.objects.filter(
            calendar=self._calendar, uid__in=uid_set, status__in=_SHARED_STATUSES
        )
        by_uid = {e.uid: e for e in events}
        for href in hrefs:
            uid = href[:-4] if href.endswith(".ics") else href
            event = by_uid.get(uid)
            if event is None:
                yield href, None
                continue
            text = event_ical_text(event)
            yield href, radicale_item.Item(
                text=text,
                href=href,
                last_modified=_http_datetime(event.updated_at),
                collection=self,
            )

    def has_uid(self, uid: str) -> bool:
        if self._calendar is None:
            return False
        return Event.objects.filter(calendar=self._calendar, uid=uid).exists()

    def upload(self, href: str, item: radicale_item.Item):
        if self._calendar is None:
            raise RuntimeError("Cannot upload to this collection")

        data, raw_text = _parse_vevent_data(item.serialize())
        uid = data["uid"] or (href[:-4] if href.endswith(".ics") else href)

        existing = Event.objects.filter(calendar=self._calendar, uid=uid).first()
        if existing is not None and existing.status not in _SHARED_STATUSES:
            # Pending, rejected and cancelled bookings are hidden from CalDAV and can't be changed here.
            raise _forbidden(f"Event {uid} cannot be changed via CalDAV")

        old_item = None
        if existing:
            rescheduled = (
                _to_utc(existing.start) != _to_utc(data["start"])
                or _to_utc(existing.end) != _to_utc(data["end"])
                or existing.all_day != data["all_day"]
                or (existing.rrule or None) != (data["rrule"] or None)
                # Another zone moves the occurrences of a series, not those of a single event.
                or (bool(data["rrule"]) and existing.timezone != data["timezone"])
            )
            resource = existing.resource
            if rescheduled and resource is not None and resource.requires_approval:
                # CalDAV doesn't tell who is writing, so it can't decide whether the new time
                # needs approval again; such bookings are rescheduled in the app.
                raise _forbidden(f"Booking {uid} must be rescheduled in the app")
            old_text = event_ical_text(existing)
            old_item = radicale_item.Item(
                text=old_text,
                href=href,
                last_modified=_http_datetime(existing.updated_at),
                collection=self,
            )
            existing.title = data["title"]
            existing.description = data["description"]
            existing.start = data["start"]
            existing.end = data["end"]
            existing.all_day = data["all_day"]
            existing.timezone = data["timezone"]
            existing.rrule = data["rrule"]
            existing.raw_ical = raw_text
            # The booking status is never changed via CalDAV.
            if rescheduled and resource is not None:
                if find_conflicting_approved_bookings(resource, existing):
                    raise ValueError(f"Booking {uid} conflicts with an approved booking")
            existing.save()
        else:
            existing = Event.objects.create(
                calendar=self._calendar,
                creator=self._calendar.owner,
                title=data["title"],
                description=data["description"],
                start=data["start"],
                end=data["end"],
                all_day=data["all_day"],
                timezone=data["timezone"],
                rrule=data["rrule"],
                uid=uid,
                raw_ical=raw_text,
                status=EventStatus.CONFIRMED,
            )

        return radicale_item.Item(
            text=raw_text,
            href=href,
            last_modified=_http_datetime(existing.updated_at),
            collection=self,
        ), old_item

    def delete(self, href: str | None = None) -> None:
        if self._calendar is None:
            return
        if href is None:
            return
        uid = href[:-4] if href.endswith(".ics") else href
        # Hidden bookings (pending, rejected, cancelled) can't be deleted via CalDAV either.
        Event.objects.filter(calendar=self._calendar, uid=uid, status__in=_SHARED_STATUSES).delete()


class Storage(storage.BaseStorage):
    @contextlib.contextmanager
    def acquire_lock(self, mode: str, user: str = "", *args, **kwargs):
        yield

    def _user_by_email(self, email: str) -> User | None:
        return User.objects.filter(email__iexact=email).first()

    def _collection_from_path(self, path: str) -> Collection | None:
        if not path or path == "/":
            return Collection(self.configuration, "/")
        parts = [p for p in path.split("/") if p]
        if len(parts) == 1:
            user = self._user_by_email(parts[0])
            if user is None:
                return None
            return Collection(self.configuration, path, user=user, is_principal=True)
        if len(parts) == 2:
            owner_email, calendar_id = parts[0], parts[1]
            owner = self._user_by_email(owner_email)
            if owner is None:
                return None
            calendar = Calendar.objects.filter(id=calendar_id, owner=owner).first()
            if calendar is None:
                return None
            return Collection(self.configuration, path, calendar=calendar)
        return None

    def discover(self, path: str, depth: str = "0", child_context_manager=None, user_groups=None):
        try:
            path = pathutils.sanitize_path(path)
            if not path or path == "/":
                root = Collection(self.configuration, "/")
                yield root
                if depth != "0":
                    owners = User.objects.filter(calendars_owned__isnull=False).distinct()
                    for user in owners:
                        yield Collection(
                            self.configuration,
                            f"/{user.email}",
                            user=user,
                            is_principal=True,
                        )
                return

            parts = [p for p in path.split("/") if p]
            if len(parts) == 1:
                coll = self._collection_from_path(path)
                if coll is not None:
                    yield coll
                if depth != "0" and coll is not None and coll.is_principal:
                    calendars = Calendar.objects.filter(owner=coll._user)
                    for calendar in calendars:
                        yield Collection(
                            self.configuration,
                            f"/{coll._user.email}/{calendar.id}",
                            calendar=calendar,
                        )
                return

            if len(parts) == 2:
                coll = self._collection_from_path(path)
                if coll is not None:
                    yield coll
                    if depth != "0":
                        for item in coll.get_all():
                            yield item
                return

            parent_path = "/" + "/".join(parts[:-1])
            href = parts[-1]
            parent = self._collection_from_path(parent_path)
            if parent is None:
                return
            for _, item in parent.get_multi([href]):
                if item is not None:
                    yield item
        finally:
            connection.close()

    def create_collection(self, href: str, items=None, props=None):
        raise RuntimeError("CalDAV calendar creation is disabled")

    def move(self, item, to_collection, to_href: str) -> None:
        raise NotImplementedError

    def verify(self) -> bool:
        return True
