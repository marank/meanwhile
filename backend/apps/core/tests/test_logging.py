"""
The log in the container's output: times in UTC like nginx's and supervisord's lines, and the
embedded CalDAV server only with what needs attention.
"""

import logging
import os
import time
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from apps.core.log_filters import UTCFormatter


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
def test_times_are_utc_whatever_the_local_zone() -> None:
    record = logging.makeLogRecord({"msg": "started", "levelname": "INFO", "name": "app"})
    record.created = datetime(2026, 11, 25, 11, 9, 44, tzinfo=UTC).timestamp()
    record.msecs = 0
    line = UTCFormatter("{asctime} {message}", style="{").format(record)
    assert line == "2026-11-25 11:09:44,000 started"


def test_the_caldav_server_logs_only_warnings_at_info() -> None:
    radicale = logging.getLogger("radicale")
    assert not radicale.isEnabledFor(logging.INFO)
    assert radicale.isEnabledFor(logging.WARNING)
