"""Filters and the format of the log output (config.settings.LOGGING)."""

import logging
import time
from typing import Any


class HideJobArguments(logging.Filter):
    """
    Logs task queue jobs by name and id only. procrastinate writes out a job's arguments with every
    start and end, and those of send_email are a whole email: addresses, event details, RSVP links.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        job: Any = getattr(record, "job", None)
        if isinstance(job, dict) and job.get("call_string"):
            short = f"{job['task_name']}[{job['id']}]"
            record.msg = str(record.msg).replace(job["call_string"], short)
            record.job = {**job, "task_kwargs": None, "call_string": short}
        return True


class OffsetFormatter(logging.Formatter):
    """
    Times in the server's zone (TIME_ZONE, which Django and the container's entrypoint make the local
    one) with their offset to UTC, e.g. "2026-11-25 14:05:12,345 +0100": easy to read, and unambiguous
    in the hour that the end of daylight saving time repeats.
    """

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        moment = self.converter(record.created)
        stamp = time.strftime(datefmt or "%Y-%m-%d %H:%M:%S", moment)
        return f"{stamp},{int(record.msecs):03d} {time.strftime('%z', moment)}"
