"""
Free/busy queries.
"""

from datetime import datetime

from apps.core.schemas.common import Id, Schema


class AvailabilityIn(Schema):
    """A query, sent as a body: the lists of ids would make for long URLs (and land in access logs)."""

    start: datetime
    end: datetime
    user_ids: list[Id] = []
    resource_ids: list[Id] = []
    # An event being edited doesn't count as taking its own time.
    exclude_event_id: Id | None = None


class BusyPeriod(Schema):
    start: datetime
    end: datetime
    # Pending bookings, invitations not answered yet and events shown as tentative.
    tentative: bool
    # Taken by an event shown as "out of office".
    out_of_office: bool = False


class AvailabilityEntry(Schema):
    id: Id
    name: str
    busy: list[BusyPeriod]


class AvailabilityOut(Schema):
    users: list[AvailabilityEntry]
    resources: list[AvailabilityEntry]
