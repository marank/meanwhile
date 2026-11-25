"""
Deleting events and changing or removing occurrences of a series, with the activity log and the iTIP
messages that tell participants.
"""

from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils.translation import gettext
from ninja.errors import HttpError

from apps.core.models import Event, User
from apps.core.models.base import EventStatus
from apps.core.schemas import OccurrenceScope
from apps.core.services import events
from apps.core.services.activity import record_activity
from apps.core.services.itip import send_cancel, send_request
from apps.core.services.recurrence import as_utc, occurrence_index
from apps.core.services.series import end_before, override_for, remove_occurrence, split

# Called off: participants were told already.
GONE = {EventStatus.REJECTED, EventStatus.CANCELLED}


def _details(start: datetime) -> dict[str, str]:
    return {"occurrence": as_utc(start).isoformat()}


def _delete_with_cancel(event: Event) -> None:
    # A cancelled or rejected event was called off already; participants don't hear it twice.
    if event.status not in GONE:
        send_cancel(event)
    event.delete()


@transaction.atomic
def delete_event(event: Event, actor: User) -> None:
    if not event.parent_id:
        _delete_with_cancel(event)
        return
    series, rid = event.parent, event.recurrence_id
    # A changed occurrence belongs to a series and keeps the start it replaces.
    assert series is not None
    assert rid is not None
    # Deleting a changed occurrence removes it from the series instead of restoring it.
    remove_occurrence(series, rid)
    record_activity(series, str(actor.id), "occurrence_deleted", _details(rid))
    send_request(series, update=True)


@transaction.atomic
def change_occurrence(series: Event, rid: datetime, actor: User, data: dict[str, Any], scope: OccurrenceScope) -> Event:
    """Changes the occurrence at `rid` ("this"), it and the later ones ("following"), or all; returns
    the event that was changed. Start and end in `data` are the occurrence's new times."""
    if scope == "this":
        override = override_for(series, rid)
        events.update_event(actor, override, data)
        record_activity(series, str(actor.id), "occurrence_changed", _details(rid))
        return override
    index = occurrence_index(series, rid) if scope == "following" else 0
    if index is None:
        # A changed occurrence at a time the rule doesn't produce (a CalDAV client may store
        # one): there is no "following" to split off from it.
        raise HttpError(
            422, gettext("This occurrence is no longer part of the series' rule; change it alone or the whole series")
        )
    if scope == "following" and index > 0:
        following = split(series, rid)
        record_activity(following, str(actor.id), "created")
        record_activity(series, str(actor.id), "series_ended", _details(rid))
        send_request(series, update=True)
        events.update_event(actor, following, data)
        return following
    # The whole series: the occurrence's new times move the series by as much.
    occurrence_end = rid + (series.end - series.start)
    if "start" in data:
        data["start"] = series.start + (as_utc(data["start"]) - rid)
    if "end" in data:
        data["end"] = series.end + (as_utc(data["end"]) - occurrence_end)
    events.update_event(actor, series, data)
    return series


@transaction.atomic
def delete_occurrence(series: Event, rid: datetime, actor: User, scope: OccurrenceScope) -> None:
    """Removes the occurrence at `rid` ("this"), it and the later ones ("following"), or all."""
    if scope == "all" or (scope == "following" and occurrence_index(series, rid) == 0):
        _delete_with_cancel(series)
        return
    if scope == "following":
        end_before(series, rid)
        record_activity(series, str(actor.id), "series_ended", _details(rid))
    else:
        remove_occurrence(series, rid)
        record_activity(series, str(actor.id), "occurrence_deleted", _details(rid))
    send_request(series, update=True)
