"""
Regression for an algorithmic-complexity DoS in the recurrence maths.

`occurrence_index` / `recurrence_count` enumerate every occurrence from the series start up to the
target with dateutil's `between`, so their cost grows without bound with the distance to the target.
An hourly series is allowed (FREQ=HOURLY), and the occurrence endpoints take the target instant
straight from the URL (`/events/{id}/occurrences/{recurrence_id}`), so a single member can make the
server enumerate tens of millions of occurrences for one cheap request.

These tests take the attacker's side and fail while the work is unbounded; a fix that computes the
index arithmetically, or rejects far-future targets, makes them pass.
"""

import signal
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest

from core.models import Event
from core.services.recurrence import occurrence_index
from core.tests.helpers import World, iso

pytestmark = pytest.mark.django_db

# Comfortably above any bounded implementation (microseconds to milliseconds), far below the
# minutes the current linear scan takes for a target millennia away — so the threshold is not flaky.
BUDGET_SECONDS = 2.0


class _Timeout(Exception):
    pass


@contextmanager
def deadline(seconds: float) -> Iterator[None]:
    def handler(signum: int, frame: object) -> None:
        raise _Timeout

    previous = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def test_occurrence_index_is_bounded_for_a_far_future_target() -> None:
    start = datetime(2030, 1, 1, 9, tzinfo=UTC)
    series = Event(start=start, end=start + timedelta(hours=1), all_day=False, timezone="UTC", rrule="FREQ=HOURLY")
    far_future = start.replace(year=9999)
    try:
        with deadline(BUDGET_SECONDS):
            occurrence_index(series, far_future)
    except _Timeout:
        pytest.fail(
            f"occurrence_index did not finish within {BUDGET_SECONDS}s for a target in 9999 — "
            "it enumerates every hourly occurrence up to the target (unbounded work)"
        )


def test_the_occurrence_endpoint_does_not_enumerate_unbounded(world: World) -> None:
    owner = world["api"]["owner"]
    event = owner.post(
        f"/calendars/{world['cal']['id']}/events",
        {
            "title": "Hourly",
            "start": iso(datetime(2030, 1, 1, 9, tzinfo=UTC)),
            "end": iso(datetime(2030, 1, 1, 10, tzinfo=UTC)),
            "rrule": "FREQ=HOURLY",
        },
    ).json()
    far_future = "9999-01-01T09:00:00+00:00"
    try:
        with deadline(BUDGET_SECONDS):
            res = owner.delete(f"/events/{event['id']}/occurrences/{far_future}")
    except _Timeout:
        pytest.fail(
            f"the occurrence endpoint did not answer within {BUDGET_SECONDS}s for a target in 9999 — "
            "a single member can make the server enumerate tens of millions of occurrences"
        )
    # Once bounded, the far-future instant is simply not an occurrence of this series.
    assert res.status_code == 404
