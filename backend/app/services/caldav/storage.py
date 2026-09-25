import contextlib
from datetime import date, datetime, timezone
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

import vobject
from email.utils import format_datetime
from radicale import item as radicale_item
from radicale import pathutils, storage
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_engine
from app.models import Calendar, Event, User


def _session() -> Session:
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _http_datetime(dt: Optional[datetime]) -> str:
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


def _parse_vevent_data(text: str) -> Tuple[dict, str]:
    """Parse a VEVENT ical string and return core fields + raw text."""
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

    uid = None
    if hasattr(vevent, "uid"):
        uid = str(vevent.uid.value)

    return {
        "title": summary,
        "description": description,
        "start": start,
        "end": end,
        "all_day": all_day,
        "rrule": rrule,
        "uid": uid,
    }, text


class Collection(storage.BaseCollection):
    def __init__(
        self,
        configuration,
        db: Session,
        path: str,
        calendar: Optional[Calendar] = None,
        user: Optional[User] = None,
        is_principal: bool = False,
    ) -> None:
        self.configuration = configuration
        self._db = db
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
        import hashlib
        data = self._etag_text()
        return '"%s"' % hashlib.sha256(data.encode()).hexdigest()

    def get_meta(self, key: Optional[str] = None):
        meta: Dict[str, str] = {}
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

    def set_meta(self, props: Dict[str, str]) -> None:
        if self._calendar is None:
            return
        name = props.get("D:displayname")
        if name:
            self._calendar.name = name
        description = props.get("C:calendar-description")
        if description is not None:
            self._calendar.description = description
        self._db.commit()

    @property
    def last_modified(self) -> str:
        if self._calendar:
            return _http_datetime(self._calendar.updated_at)
        return _http_datetime(datetime.now(timezone.utc))

    def sync(self, old_token: str = "") -> Tuple[str, Iterable[str]]:
        token = "http://radicale.org/ns/sync/%s" % self.etag.strip('"')
        if old_token == token:
            return token, []
        return token, [item.href for item in self.get_all()]

    def get_all(self) -> Iterable[radicale_item.Item]:
        if self._calendar is None:
            return []
        events = (
            self._db.query(Event)
            .filter(Event.calendar_id == self._calendar.id)
            .all()
        )
        for event in events:
            text = event.raw_ical
            if not text:
                from app.services.ical import build_event_ical
                text = build_event_ical(event).to_ical().decode("utf-8")
            href = f"{event.uid}.ics"
            last_modified = _http_datetime(event.updated_at)
            yield radicale_item.Item(
                text=text,
                href=href,
                last_modified=last_modified,
                collection=self,
            )

    def get_multi(
        self, hrefs: Iterable[str]
    ) -> Iterable[Tuple[str, Optional[radicale_item.Item]]]:
        if self._calendar is None:
            for href in hrefs:
                yield href, None
            return
        requested = {h.strip("/") for h in hrefs}
        # hrefs look like "uid.ics"
        uid_set = {h[:-4] if h.endswith(".ics") else h for h in requested}
        events = (
            self._db.query(Event)
            .filter(
                Event.calendar_id == self._calendar.id,
                Event.uid.in_(uid_set),
            )
            .all()
        )
        by_uid = {e.uid: e for e in events}
        for href in hrefs:
            uid = href[:-4] if href.endswith(".ics") else href
            event = by_uid.get(uid)
            if event is None:
                yield href, None
                continue
            text = event.raw_ical
            if not text:
                from app.services.ical import build_event_ical
                text = build_event_ical(event).to_ical().decode("utf-8")
            yield href, radicale_item.Item(
                text=text,
                href=href,
                last_modified=_http_datetime(event.updated_at),
                collection=self,
            )

    def has_uid(self, uid: str) -> bool:
        if self._calendar is None:
            return False
        return (
            self._db.query(Event)
            .filter(Event.calendar_id == self._calendar.id, Event.uid == uid)
            .first()
            is not None
        )

    def upload(
        self, href: str, item: radicale_item.Item
    ) -> Tuple[radicale_item.Item, Optional[radicale_item.Item]]:
        if self._calendar is None:
            raise RuntimeError("Cannot upload to this collection")

        data, raw_text = _parse_vevent_data(item.serialize())
        uid = data["uid"] or (href[:-4] if href.endswith(".ics") else href)

        existing = (
            self._db.query(Event)
            .filter(Event.calendar_id == self._calendar.id, Event.uid == uid)
            .first()
        )

        old_item = None
        if existing:
            old_text = existing.raw_ical
            if not old_text:
                from app.services.ical import build_event_ical
                old_text = build_event_ical(existing).to_ical().decode("utf-8")
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
            existing.rrule = data["rrule"]
            existing.raw_ical = raw_text
            existing.status = "confirmed"
        else:
            existing = Event(
                calendar_id=self._calendar.id,
                creator_id=self._calendar.owner_id,
                title=data["title"],
                description=data["description"],
                start=data["start"],
                end=data["end"],
                all_day=data["all_day"],
                rrule=data["rrule"],
                uid=uid,
                raw_ical=raw_text,
                status="confirmed",
            )
            self._db.add(existing)

        self._db.commit()
        self._db.refresh(existing)

        new_item = radicale_item.Item(
            text=raw_text,
            href=href,
            last_modified=_http_datetime(existing.updated_at),
            collection=self,
        )
        return new_item, old_item

    def delete(self, href: Optional[str] = None) -> None:
        if self._calendar is None:
            return
        if href is None:
            # Deleting the whole collection is not allowed via CalDAV.
            return
        uid = href[:-4] if href.endswith(".ics") else href
        event = (
            self._db.query(Event)
            .filter(Event.calendar_id == self._calendar.id, Event.uid == uid)
            .first()
        )
        if event:
            self._db.delete(event)
            self._db.commit()


class Storage(storage.BaseStorage):
    @contextlib.contextmanager
    def acquire_lock(
        self, mode: str, user: str = "", *args, **kwargs
    ) -> Iterator[None]:
        yield

    def _user_by_email(self, db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    def _collection_from_path(
        self, db: Session, path: str
    ) -> Optional[Collection]:
        # path is already sanitized (leading slash, no trailing slash)
        if not path or path == "/":
            return Collection(self.configuration, db, "/")
        parts = [p for p in path.split("/") if p]
        if len(parts) == 1:
            user = self._user_by_email(db, parts[0])
            if user is None:
                return None
            return Collection(
                self.configuration,
                db,
                path,
                user=user,
                is_principal=True,
            )
        if len(parts) == 2:
            owner_email = parts[0]
            calendar_id = parts[1]
            owner = self._user_by_email(db, owner_email)
            if owner is None:
                return None
            calendar = (
                db.query(Calendar)
                .filter(Calendar.id == calendar_id, Calendar.owner_id == owner.id)
                .first()
            )
            if calendar is None:
                return None
            return Collection(
                self.configuration,
                db,
                path,
                calendar=calendar,
            )
        # Paths deeper than two components refer to individual items, not
        # collections.
        return None

    def discover(
        self,
        path: str,
        depth: str = "0",
        child_context_manager=None,
        user_groups=None,
    ) -> Iterable[storage.BaseCollection]:
        db = _session()
        try:
            path = pathutils.sanitize_path(path)
            if not path or path == "/":
                root = Collection(self.configuration, db, "/")
                yield root
                if depth != "0":
                    # Yield principals for every user who owns at least one
                    # calendar. The rights plugin filters them.
                    owners = (
                        db.query(User)
                        .join(Calendar, Calendar.owner_id == User.id)
                        .distinct()
                        .all()
                    )
                    for user in owners:
                        yield Collection(
                            self.configuration,
                            db,
                            f"/{user.email}",
                            user=user,
                            is_principal=True,
                        )
                return

            parts = [p for p in path.split("/") if p]
            if len(parts) == 1:
                coll = self._collection_from_path(db, path)
                if coll is not None:
                    yield coll
                if depth != "0" and coll is not None and coll.is_principal:
                    user = coll._user
                    calendars = (
                        db.query(Calendar)
                        .filter(Calendar.owner_id == user.id)
                        .all()
                    )
                    for calendar in calendars:
                        yield Collection(
                            self.configuration,
                            db,
                            f"/{user.email}/{calendar.id}",
                            calendar=calendar,
                        )
                return

            if len(parts) == 2:
                coll = self._collection_from_path(db, path)
                if coll is not None:
                    yield coll
                    if depth != "0":
                        for item in coll.get_all():
                            yield item
                return

            # Path refers to an individual item within a calendar.
            parent_path = "/" + "/".join(parts[:-1])
            href = parts[-1]
            parent = self._collection_from_path(db, parent_path)
            if parent is None:
                return
            for _, item in parent.get_multi([href]):
                if item is not None:
                    yield item
        finally:
            db.close()

    def create_collection(
        self,
        href: str,
        items: Optional[Iterable[radicale_item.Item]] = None,
        props: Optional[Dict[str, str]] = None,
    ) -> Tuple[Collection, Dict[str, radicale_item.Item], List[str]]:
        # Calendar creation is only supported via the web UI.
        raise RuntimeError("CalDAV calendar creation is disabled")

    def move(
        self,
        item: radicale_item.Item,
        to_collection: storage.BaseCollection,
        to_href: str,
    ) -> None:
        raise NotImplementedError

    def verify(self) -> bool:
        return True
