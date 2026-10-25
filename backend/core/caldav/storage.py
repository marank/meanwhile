"""
Radicale storage plugin backed by the Django ORM.
"""

import contextlib
import errno
import functools
import hashlib
import json
import re
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import AbstractContextManager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import Any, overload

import icalendar
from django.db import transaction
from django.db.models import Max, Prefetch, Q, QuerySet
from django.utils import timezone
from radicale import config, pathutils, storage, types
from radicale import item as radicale_item

from core.caldav.parsing import EventData, parse_series, to_utc
from core.caldav.request import once_per_request
from core.models import Calendar, Category, DeletedEvent, Event, EventParticipant, EventReminder, User, as_uuid
from core.models.base import EventStatus, Role
from core.realtime import broadcast
from core.services.activity import record_activity
from core.services.bookings import booked_resources, find_booking_conflicts
from core.services.calendars import create_calendar
from core.services.ical import PRODID, VTIMEZONE_UNTIL, event_ical_text
from core.services.notifications import notify
from core.services.permissions import (
    accessible_calendars,
    can_modify_event,
    get_membership,
    has_at_least_role,
    sidebar_calendars,
)
from core.services.recurrence import format_exdate, is_series, parse_exdates
from core.signals import DELETED_EVENT_RETENTION

# CalDAV only knows the calendar, not who is asking, so it shares what everyone may see,
# like the ICS feed: pending, rejected and cancelled bookings stay out.
_SHARED_STATUSES = {EventStatus.CONFIRMED, EventStatus.APPROVED}

_SYNC_TOKEN_PREFIX = "http://radicale.org/ns/sync/"
# Transactions may commit in another order than their timestamps; a sync looks back this far
# so that a change committed late is still reported.
_SYNC_OVERLAP = timedelta(seconds=30)


# Login of the user the current request runs for; Radicale hands it to Storage.acquire_lock.
_acting_login: ContextVar[str] = ContextVar("caldav_acting_login", default="")


@contextlib.contextmanager
def acting_as(login: str) -> Iterator[None]:
    token = _acting_login.set(login or "")
    try:
        yield
    finally:
        _acting_login.reset(token)


class Forbidden(ValueError):
    """A write the acting user may not make; answered with 403 Forbidden."""


def _forbidden(message: str) -> Forbidden:
    # Radicale answers a ValueError carrying EACCES from PUT with 403; core.caldav.app does so for the rest.
    return Forbidden(f"[Errno {errno.EACCES}] {message}")


def _http_datetime(dt: datetime | None) -> str:
    if dt is None:
        return format_datetime(timezone.now())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return format_datetime(dt)


def _hex_color(value: str | None) -> str | None:
    """ "#rrggbb" from a client's color; Apple adds an alpha channel ("#FF2968FF")."""
    if not value or not re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", value.strip()):
        return None
    return value.strip()[:7].lower()


def _fields(event: Event) -> dict[str, object]:
    """What a client changes of an event, to record which of it changed."""
    return {
        "title": event.title,
        "description": event.description,
        "start": event.start,
        "end": event.end,
        "all_day": event.all_day,
        "rrule": event.rrule,
        "location": event.location,
        "category": event.category_id,
    }


@functools.lru_cache(maxsize=64)
def calendar_timezone(name: str) -> str:
    """A VCALENDAR with the VTIMEZONE of the IANA zone `name`, as CalDAV's calendar-timezone holds it."""
    cal = icalendar.Calendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")
    cal.add_component(icalendar.Timezone.from_tzid(name, last_date=VTIMEZONE_UNTIL))
    data: bytes = cal.to_ical()
    return data.decode()


def _dav_name(calendar: Calendar, home: User) -> str:
    """A calendar's path segment in the user's calendar home: the name a client gave it in its owner's
    home (names are the owner's own), the id everywhere else."""
    if calendar.dav_name and calendar.owner_id == home.id:
        return calendar.dav_name
    return str(calendar.id)


def user_by_email(email: str) -> User | None:
    return once_per_request(("user", email.lower()), lambda: User.objects.filter(email__iexact=email).first())


def calendar_in_home(home: User, name: str, calendars: QuerySet[Calendar] | None = None) -> Calendar | None:
    """The calendar a path segment in the user's calendar home names: its id, else the name a client
    gave one of the user's own calendars (clients pick names like UUIDs, too)."""
    calendars = Calendar.objects.all() if calendars is None else calendars
    calendar_id = as_uuid(name)
    by_id = calendars.filter(id=calendar_id).first() if calendar_id else None
    return by_id or calendars.filter(owner=home, dav_name=name).first()


class _Item(radicale_item.Item):
    """Radicale's REPORT expands recurring events once per requested property, each time on a
    shallow copy.copy() of the item, and the expansion changes the copy's iCalendar object, which
    the original shares; the second property (e.g. calendar-data after getetag) then fails. A copy
    of its own iCalendar object for each copy keeps them apart."""

    def __copy__(self) -> _Item:
        return _Item(
            text=self.serialize(),
            href=self.href,
            last_modified=self.last_modified,
            collection=self.collection,
        )


class Collection(storage.BaseCollection):
    def __init__(
        self,
        configuration: config.Configuration,
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
        # Who the request runs for, remembered: Radicale builds parts of its answer (PROPFIND's
        # properties) after it has let go of the storage (acquire_lock), when that is forgotten.
        self._login = _acting_login.get()
        # Radicale asks for both several times per request (e.g. a PROPFIND lists all items three times).
        self._state_cache: tuple[int, str] | None = None
        self._items_cache: list[radicale_item.Item] | None = None

    def _forget(self) -> None:
        """After a write, the collection is read afresh."""
        self._state_cache = self._items_cache = None

    @property
    def path(self) -> str:
        return self._path

    @property
    def is_principal(self) -> bool:
        return self._is_principal or (bool(self.path) and "/" not in self.path)

    def _state(self) -> tuple[int, str]:
        """When the calendar last changed (in microseconds) and a digest of what clients see of it."""
        if self._state_cache is None:
            self._state_cache = self._compute_state()
        return self._state_cache

    def _compute_state(self) -> tuple[int, str]:
        digest = hashlib.sha256(json.dumps(self.get_meta(), sort_keys=True).encode())
        if self._calendar is None:
            return 0, digest.hexdigest()
        # Item content only changes along with updated_at, so hrefs and timestamps identify it.
        rows = (
            Event.objects.filter(calendar=self._calendar, parent__isnull=True, status__in=_SHARED_STATUSES)
            .order_by("id")
            .values_list("href", "uid", "updated_at")
        )
        for href, uid, updated_at in rows:
            digest.update(f"{href or uid + '.ics'}/{updated_at.isoformat()}\n".encode())
        latest = [
            self._calendar.updated_at,
            # Hidden events count too: a booking that turns hidden must be removed from clients.
            Event.objects.filter(calendar=self._calendar).aggregate(m=Max("updated_at"))["m"],
            DeletedEvent.objects.filter(calendar_id=self._calendar.id).aggregate(m=Max("deleted_at"))["m"],
        ]
        changed_at = max(to_utc(t) for t in latest if t is not None)
        return int(changed_at.timestamp() * 1_000_000), digest.hexdigest()

    @property
    def etag(self) -> str:
        return f'"{self._state()[1]}"'

    @overload
    def get_meta(self, key: None = None) -> Mapping[str, str]: ...

    @overload
    def get_meta(self, key: str) -> str | None: ...

    def get_meta(self, key: str | None = None) -> Mapping[str, str] | str | None:
        meta: dict[str, str] = {}
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
                "ICAL:calendar-color": self._calendar.event_color,
            }
            # The zone clients read times without one in (RFC 4791 5.2.2): the viewer's, as the app has it.
            viewer = self._viewer()
            if viewer is not None and viewer.timezone:
                meta["C:calendar-timezone"] = calendar_timezone(viewer.timezone)
        if key is None:
            return meta
        return meta.get(key)

    def set_meta(self, props: Mapping[str, str]) -> None:
        if self._calendar is None:
            return
        _, role = self._actor()
        if role not in {Role.OWNER, Role.MANAGE}:
            # Same rule as the API: only who manages the calendar changes its details.
            raise _forbidden("Only who manages the calendar can change its details")
        name = props.get("D:displayname")
        if name:
            self._calendar.name = name
        description = props.get("C:calendar-description")
        if description is not None:
            self._calendar.description = description
        color = _hex_color(props.get("ICAL:calendar-color"))
        if color and color != self._calendar.event_color:
            # Clients show one color per calendar: the color of its events, in both themes.
            self._calendar.event_color = color
            self._calendar.dark_event_color = color
        self._calendar.save()
        self._forget()

    @property
    def last_modified(self) -> str:
        if self._calendar:
            return _http_datetime(self._calendar.updated_at)
        return _http_datetime(timezone.now())

    def sync(self, old_token: str = "") -> tuple[str, list[str]]:
        changed_at, digest = self._state()
        token = f"{_SYNC_TOKEN_PREFIX}{changed_at}-{digest}"
        if not old_token or self._calendar is None:
            return token, [item.href for item in self.get_all() if item.href is not None]
        if old_token == token:
            return token, []
        # Radicale answers a ValueError with "invalid sync token", and the client syncs everything.
        try:
            since_micros = int(old_token.removeprefix(_SYNC_TOKEN_PREFIX).split("-", 1)[0])
            since = datetime.fromtimestamp(since_micros / 1_000_000, UTC)
        except (ValueError, OverflowError, OSError) as exc:
            raise ValueError(f"Unknown sync token {old_token!r}") from exc
        if since < timezone.now() - DELETED_EVENT_RETENTION:
            raise ValueError("Sync token is older than the record of deleted events")
        since -= _SYNC_OVERLAP
        # Events no longer shown (deleted, or bookings now pending, rejected or cancelled) are
        # reported too; Radicale answers them with 404, which tells the client to drop them.
        changed = {
            href or f"{uid}.ics"
            for href, uid in Event.objects.filter(
                calendar=self._calendar, parent__isnull=True, updated_at__gt=since
            ).values_list("href", "uid")
        }
        changed.update(
            DeletedEvent.objects.filter(calendar_id=self._calendar.id, deleted_at__gt=since).values_list(
                "href", flat=True
            )
        )
        return token, sorted(changed)

    def _viewer(self) -> User | None:
        """The user the request runs for; each user's reminders are written as their alarms."""
        login = _acting_login.get() or self._login
        return user_by_email(login) if login else None

    def _events(self) -> QuerySet[Event]:
        """The calendar's series and single events, with what writing them needs."""
        viewer = self._viewer()
        return (
            Event.objects.filter(calendar=self._calendar, parent__isnull=True)
            .select_related("category", "resource", "location_resource", "creator")
            .prefetch_related(
                Prefetch(
                    "overrides", queryset=Event.objects.select_related("category", "resource", "location_resource")
                ),
                "participants__user",
                "overrides__participants__user",
                Prefetch(
                    "reminders",
                    queryset=EventReminder.objects.filter(user=viewer) if viewer else EventReminder.objects.none(),
                    to_attr="viewer_reminders",
                ),
            )
        )

    def _item(self, event: Event) -> radicale_item.Item:
        # Only a calendar's collection has items.
        assert self._calendar is not None
        # One calendar object for all items, so that what is looked up of it is looked up once.
        event.calendar = self._calendar
        return _Item(
            text=event_ical_text(event, self._viewer()),
            href=event.dav_href,
            last_modified=_http_datetime(event.updated_at),
            collection=self,
        )

    def _events_by_href(self, hrefs: list[str], shared_only: bool = True) -> dict[str, Event]:
        # Events created in the app have no href of their own and are found by "{uid}.ics".
        uids = {h[:-4] for h in hrefs if h.endswith(".ics")}
        events = self._events().filter(
            Q(href__in=hrefs) | (Q(href__isnull=True) | Q(href="")) & Q(uid__in=uids),
        )
        if shared_only:
            events = events.filter(status__in=_SHARED_STATUSES)
        return {e.dav_href: e for e in events}

    def get_all(self) -> list[radicale_item.Item]:
        if self._calendar is None:
            return []
        if self._items_cache is None:
            self._items_cache = [self._item(e) for e in self._events().filter(status__in=_SHARED_STATUSES)]
        return self._items_cache

    def get_multi(self, hrefs: Iterable[str]) -> Iterator[tuple[str, radicale_item.Item | None]]:
        # Radicale passes a generator, and the hrefs are read twice below.
        wanted = list(hrefs)
        if self._calendar is None:
            for href in wanted:
                yield href, None
            return
        by_href = self._events_by_href(wanted)
        for href in wanted:
            event = by_href.get(href)
            yield href, self._item(event) if event is not None else None

    def _actor(self) -> tuple[User, str]:
        """The user writing to this calendar and their role; writes need at least the role "own"."""
        # Only a calendar's collection is written to.
        assert self._calendar is not None
        user = self._viewer()
        if user is None or not user.is_active:
            raise _forbidden("No write access to this calendar")
        membership = get_membership(self._calendar, user)
        if membership is None or not has_at_least_role(membership, Role.OWN):
            raise _forbidden("No write access to this calendar")
        return user, membership.role

    def has_uid(self, uid: str) -> bool:
        if self._calendar is None:
            return False
        return Event.objects.filter(calendar=self._calendar, parent__isnull=True, uid=uid).exists()

    def upload(self, href: str, item: radicale_item.Item) -> tuple[radicale_item.Item, radicale_item.Item | None]:
        if self._calendar is None:
            raise RuntimeError("Cannot upload to this collection")

        actor, role = self._actor()
        raw_text = item.serialize()
        # Times without a zone are meant in the writer's own zone.
        data, overrides = parse_series(raw_text, actor.timezone or "UTC")
        uid = data["uid"] or (href[:-4] if href.endswith(".ics") else href)
        if len(uid) > 255 or len(href) > 255:
            raise ValueError("UID and file name may have at most 255 characters")
        if self._calendar.force_all_day and not all(c["all_day"] for c in [data, *overrides]):
            raise _forbidden(f"Calendar {self._calendar.id} only allows all-day events")

        existing = self._events_by_href([href], shared_only=False).get(href)
        if existing is not None and existing.status not in _SHARED_STATUSES:
            # Pending, rejected and cancelled bookings are hidden from CalDAV and can't be changed here.
            raise _forbidden(f"Event {uid} cannot be changed via CalDAV")
        if existing is not None and not can_modify_event(existing, str(actor.id), role):
            # Same rule as the API: users with the role "own" only change their own events.
            raise _forbidden(f"Event {uid} may only be changed by its creator or a user with full access")

        old_item = None
        created = existing is None
        with transaction.atomic():
            if existing:
                rdates = sorted(format_exdate(d) for d in data["rdates"])
                rescheduled = (
                    to_utc(existing.start) != to_utc(data["start"])
                    or to_utc(existing.end) != to_utc(data["end"])
                    or existing.all_day != data["all_day"]
                    or (existing.rrule or None) != (data["rrule"] or None)
                    or (existing.rdates or []) != rdates
                    # Another zone moves the occurrences of a series, not those of a single event.
                    or (bool(data["rrule"]) and existing.timezone != data["timezone"])
                )
                booked = booked_resources(existing)
                if rescheduled and any(r.requires_approval for r in booked):
                    # A new time may need approval again, which would hide the booking from the client
                    # that just wrote it; such bookings are rescheduled in the app.
                    raise _forbidden(f"Booking {uid} must be rescheduled in the app")
                old_item = self._item(existing)
                before = _fields(existing)
                self._apply(existing, data)
                existing.raw_ical = raw_text
                # The booking status is never changed via CalDAV.
                if rescheduled and booked:
                    if find_booking_conflicts(existing):
                        raise ValueError(f"Booking {uid} conflicts with an approved booking")
            else:
                existing = Event(
                    calendar=self._calendar,
                    creator=actor,
                    uid=uid,
                    href=href,
                    raw_ical=raw_text,
                    status=EventStatus.CONFIRMED,
                )
                self._apply(existing, data)
            removed, changed = self._store_exceptions(existing, data, overrides, actor)
            self._store_participants(existing, data, actor)
            self._store_reminders(existing, actor, data["alarms"])

            if created:
                record_activity(existing, str(actor.id), "created")
            else:
                fields = [name for name, value in _fields(existing).items() if before[name] != value]
                if fields:
                    record_activity(existing, str(actor.id), "updated", {"fields": fields})
                for kind, starts in (("occurrence_deleted", removed), ("occurrence_changed", changed)):
                    for start in sorted(starts):
                        record_activity(existing, str(actor.id), kind, {"occurrence": start.isoformat()})

        self._forget()
        return self._item(Event.objects.get(pk=existing.pk)), old_item

    def _category(self, names: list[str]) -> Category | None:
        """The calendar's category among the client's CATEGORIES, if one of them is."""
        assert self._calendar is not None  # an upload, which needs a calendar
        wanted = [n.lower() for n in names]
        by_name = {c.name.lower(): c for c in self._calendar.categories.all()}
        return next((by_name[n] for n in wanted if n in by_name), None)

    def _apply(self, event: Event, data: EventData) -> None:
        event.title = data["title"]
        event.description = data["description"]
        event.start = data["start"]
        event.end = data["end"]
        event.all_day = data["all_day"]
        event.timezone = data["timezone"]
        event.category = self._category(data["categories"])
        # A booked location is changed in the app only; otherwise the client's location is the event's.
        if event.location_resource_id is None:
            event.location = data["location"]
        if not event.parent_id:
            event.rrule = data["rrule"]
            event.rdates = sorted(format_exdate(d) for d in data["rdates"])

    def _store_exceptions(
        self, series: Event, data: EventData, overrides: list[EventData], actor: User
    ) -> tuple[set[datetime], set[datetime]]:
        """Saves the series with the removed and changed occurrences the client sent.

        Returns the starts of the occurrences that were newly removed and those changed.
        """
        current = {o.recurrence_id: o for o in series.overrides.all()} if series.pk else {}
        old_exdates = parse_exdates(series.exdates)
        # Changes others may not see (e.g. a pending booking) are served as removed occurrences;
        # they come back as EXDATE and stay as they are.
        hidden = {rid for rid, o in current.items() if o.status not in _SHARED_STATUSES}
        exdates = data["exdates"] - hidden if is_series(series) else set()
        series.exdates = sorted(format_exdate(d) for d in exdates)
        series.save()

        incoming = {rid: o for o in overrides if (rid := o["recurrence_id"]) is not None and rid not in hidden}
        for rid, stale in current.items():
            if rid not in incoming and rid not in hidden:
                stale.delete()

        booked = booked_resources(series)
        duration = series.end - series.start
        changed: set[datetime] = set()
        for rid, override_data in incoming.items():
            override = current.get(rid)
            before = (
                (override.start, override.end, override.all_day) if override else (rid, rid + duration, series.all_day)
            )
            moved = before != (override_data["start"], override_data["end"], override_data["all_day"])
            if moved and any(r.requires_approval for r in booked):
                raise _forbidden(f"Booking {series.uid} must be rescheduled in the app")
            if override is None:
                override = Event(
                    calendar=series.calendar,
                    creator=actor,
                    parent=series,
                    recurrence_id=rid,
                    uid=series.uid,
                    status=series.status,
                    resource=series.resource,
                    location_resource=series.location_resource,
                    awaiting_approval=list(series.awaiting_approval or []),
                )
                old_fields = None
            else:
                old_fields = _fields(override)
            self._apply(override, override_data)
            if moved and booked and find_booking_conflicts(override):
                raise ValueError(f"Booking {series.uid} conflicts with an approved booking")
            override.save()
            self._store_participants(override, override_data, actor)
            if old_fields != _fields(override):
                changed.add(rid)
        return exdates - old_exdates, changed

    def _store_participants(self, event: Event, data: EventData, actor: User) -> None:
        """Makes the event's participants those the client lists as attendees."""
        organizer = data["organizer"] or event.creator.email.lower()
        wanted = {email: status for email, status in data["attendees"] if email and email != organizer}
        current = {p.email.lower(): p for p in event.participants.all()}
        for email, stale in current.items():
            if email not in wanted:
                stale.delete()
        for email, status in wanted.items():
            participant = current.get(email)
            if participant is not None:
                # A participant's answer is theirs: a client that sends the event back with an old
                # PARTSTAT (it hadn't seen the answer yet) doesn't undo it.
                if participant.status != status and email == actor.email.lower():
                    participant.status = status
                    participant.save()
                continue
            user = User.objects.filter(email__iexact=email).first()
            EventParticipant.objects.create(event=event, user=user, email=email, status=status)
            if user is not None:
                notify(
                    [str(user.id)],
                    "participant_added",
                    str(actor.id),
                    event.title or "Untitled event",
                    calendar_id=str(event.calendar_id),
                    event_id=str(event.id),
                    data={"email": email},
                )

    def _store_reminders(self, series: Event, actor: User, minutes: list[int] | None) -> None:
        """The writer's reminders are the alarms the client sent; others' reminders stay as they are."""
        EventReminder.objects.filter(event=series, user=actor).exclude(minutes_before__in=minutes or []).delete()
        for before in minutes or []:
            EventReminder.objects.get_or_create(event=series, user=actor, minutes_before=before)

    def delete(self, href: str | None = None) -> None:
        if self._calendar is None:
            raise _forbidden("Only events and calendars can be deleted")
        if href is None:
            # The whole calendar: same rule as the API, only its owner deletes it.
            _, role = self._actor()
            if role != Role.OWNER:
                raise _forbidden("Only the owner can delete this calendar")
            self._calendar.delete()
            return
        # Hidden bookings (pending, rejected, cancelled) can't be deleted via CalDAV either.
        event = self._events_by_href([href]).get(href)
        if event is None:
            return
        actor, role = self._actor()
        if not can_modify_event(event, str(actor.id), role):
            raise _forbidden(f"Event {href} may only be deleted by its creator or a user with full access")
        event.delete()
        self._forget()


class Storage(storage.BaseStorage):
    @contextlib.contextmanager
    def acquire_lock(self, mode: str, user: str = "", *args: Any, **kwargs: Any) -> Iterator[None]:
        # The database does the locking; this only remembers who the request runs for.
        with acting_as(user):
            yield

    def _collection_from_path(self, path: str) -> Collection | None:
        if not path or path == "/":
            return Collection(self.configuration, "/")
        parts = [p for p in path.split("/") if p]
        if len(parts) == 1:
            user = user_by_email(parts[0])
            if user is None:
                return None
            return Collection(self.configuration, path, user=user, is_principal=True)
        if len(parts) == 2:
            # Calendars are served under their owner and under every user who has access to them,
            # so each user's calendar home lists the calendars shared with them, too.
            user = user_by_email(parts[0])
            if user is None:
                return None
            calendar = calendar_in_home(user, parts[1], accessible_calendars(user))
            if calendar is None:
                return None
            return Collection(self.configuration, path, calendar=calendar)
        return None

    def discover(
        self,
        path: str,
        depth: str = "0",
        child_context_manager: Callable[[str, str | None], AbstractContextManager[None]] | None = None,
        user_groups: set[str] | None = None,
    ) -> Iterator[types.CollectionOrItem]:
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
                owner = coll._user
                assert owner is not None  # principals are users
                # The calendars of the sidebar; another public one is still found by its address.
                for calendar in sidebar_calendars(owner).order_by("name"):
                    yield Collection(
                        self.configuration,
                        f"/{owner.email}/{_dav_name(calendar, owner)}",
                        calendar=calendar,
                    )
            return

        if len(parts) == 2:
            coll = self._collection_from_path(path)
            if coll is not None:
                yield coll
                if depth != "0":
                    yield from coll.get_all()
            return

        parent_path = "/" + "/".join(parts[:-1])
        href = parts[-1]
        parent = self._collection_from_path(parent_path)
        if parent is None:
            return
        for _, found in parent.get_multi([href]):
            if found is not None:
                yield found

    def create_collection(
        self,
        href: str,
        items: Iterable[radicale_item.Item] | None = None,
        props: Mapping[str, str] | None = None,
    ) -> tuple[Collection, dict[str, radicale_item.Item], list[str]]:
        """Creates a calendar for a client (MKCALENDAR, or MKCOL from the Radicale web interface).

        Returns it as Radicale expects: with the items it replaced and the hrefs of new ones (none here).
        """
        parts = [p for p in pathutils.strip_path(href).split("/") if p]
        if len(parts) == 1:
            # Radicale asks for a principal on first login; every user already has one.
            principal = self._collection_from_path(href)
            if principal is None:
                raise _forbidden("Calendar homes are those of users")
            return principal, {}, []
        props = props or {}
        if len(parts) != 2 or props.get("tag") != "VCALENDAR":
            raise _forbidden("Only calendars can be created, directly in the calendar home")
        if items is not None:
            raise _forbidden("Calendars can't be uploaded as a whole; create one and add its events")
        components = props.get("C:supported-calendar-component-set")
        if components and "VEVENT" not in components.split(","):
            # e.g. a task list (VTODO) from a reminders app
            raise _forbidden("Calendars hold events only")
        owner = User.objects.filter(email__iexact=_acting_login.get(), is_active=True).first()
        if owner is None or owner.email.lower() != parts[0].lower():
            raise _forbidden("Calendars are created in your own calendar home only")
        # Nor may the name be another calendar's id, which names that calendar in every path.
        # Names are the owner's own; nor may one be another calendar's id, which names it in every home.
        if Calendar.objects.filter(owner=owner, dav_name=parts[1]).exists() or (
            (calendar_id := as_uuid(parts[1])) and Calendar.objects.filter(id=calendar_id).exists()
        ):
            raise pathutils.CollidingPathError(href)
        calendar = create_calendar(
            owner,
            name=props.get("D:displayname") or parts[1],
            description=props.get("C:calendar-description") or "",
            dav_name=parts[1],
        )
        return Collection(self.configuration, href, calendar=calendar), {}, []

    def move(self, item: radicale_item.Item, to_collection: storage.BaseCollection, to_href: str) -> None:
        """Renames an event or moves it to another calendar, e.g. when a client changes its calendar."""
        source = item.collection
        # Every collection is one of this storage's.
        assert isinstance(source, Collection) and isinstance(to_collection, Collection)
        assert item.href is not None
        target = to_collection._calendar
        event = source._events_by_href([item.href]).get(item.href)
        if event is None or target is None:
            raise ValueError(f"Cannot move {item.href}")
        actor, role = source._actor()
        if not can_modify_event(event, str(actor.id), role):
            raise _forbidden(f"Event {item.href} may only be moved by its creator or a user with full access")
        _, target_role = to_collection._actor()

        moving = target.id != event.calendar_id
        if moving:
            if (
                booked_resources(event)
                or event.overrides.filter(Q(resource__isnull=False) | Q(location_resource__isnull=False)).exists()
            ):
                # Resources belong to their calendar, and so do the bookings of them.
                raise _forbidden("Bookings can't be moved to another calendar")
            if target.force_all_day and (event.all_day is False or event.overrides.filter(all_day=False).exists()):
                raise _forbidden(f"Calendar {target.id} only allows all-day events")

        old_calendar_id, old_href = event.calendar_id, event.dav_href
        with transaction.atomic():
            replaced = to_collection._events_by_href([to_href], shared_only=False).get(to_href)
            if replaced is not None and replaced.pk != event.pk:
                # Radicale only gets here with "Overwrite: T".
                if not can_modify_event(replaced, str(actor.id), target_role):
                    raise _forbidden(f"Event {to_href} may only be replaced by its creator or a user with full access")
                replaced.delete()
            if moving:
                event.calendar = target
                # Categories belong to their calendar.
                event.category = None
                event.overrides.update(calendar=target, category=None)
            event.href = to_href
            event.save()
            if moving or old_href != to_href:
                # Clients syncing the old place learn that the event is gone from there.
                DeletedEvent.objects.create(calendar_id=old_calendar_id, href=old_href)
            # Saving tells the new calendar's readers; the old one's must hear it, too.
            broadcast.calendar_changed(old_calendar_id)
        source._forget()
        to_collection._forget()

    def verify(self) -> bool:
        return True
