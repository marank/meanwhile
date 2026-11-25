"""
The log in the container's output: times in the server's zone with their offset to UTC, and the
embedded CalDAV server only with what needs attention.
"""

import logging
import os
import time
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from apps.core.log_filters import OffsetFormatter


@pytest.fixture
def berlin() -> Iterator[None]:
    # As Django does with TIME_ZONE: the process's local time.
    before = os.environ.get("TZ")
    os.environ["TZ"] = "Europe/Berlin"
    time.tzset()
    yield
    if before is None:
        del os.environ["TZ"]
    else:
        os.environ["TZ"] = before
    time.tzset()


@pytest.mark.usefixtures("berlin")
def test_times_are_local_with_their_offset() -> None:
    def line(moment: datetime) -> str:
        record = logging.makeLogRecord({"msg": "started", "levelname": "INFO", "name": "app"})
        record.created = moment.timestamp()
        record.msecs = 0
        return OffsetFormatter("{asctime} {message}", style="{").format(record)

    assert line(datetime(2026, 11, 25, 11, 9, 44, tzinfo=UTC)) == "2026-11-25 12:09:44,000 +0100 started"
    # The hour daylight saving time repeats is told apart by the offset.
    assert line(datetime(2026, 10, 25, 0, 30, tzinfo=UTC)) == "2026-10-25 02:30:00,000 +0200 started"
    assert line(datetime(2026, 10, 25, 1, 30, tzinfo=UTC)) == "2026-10-25 02:30:00,000 +0100 started"


def test_the_caldav_server_logs_only_warnings_at_info() -> None:
    radicale = logging.getLogger("radicale")
    assert not radicale.isEnabledFor(logging.INFO)
    assert radicale.isEnabledFor(logging.WARNING)
