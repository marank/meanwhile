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


class UTCFormatter(logging.Formatter):
    """
    Times in UTC, like nginx's and supervisord's lines in the container's output. Django sets the
    process's local zone to TIME_ZONE, which would put the app's lines an hour or two off theirs.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.converter = time.gmtime
