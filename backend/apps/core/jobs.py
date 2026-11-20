"""
Deferring jobs of the task queue (the tasks themselves live in apps/core/tasks.py).

With PostgreSQL (settings.JOB_QUEUE) a job goes into procrastinate's queue within the current
transaction: it exists only once the change that caused it is committed, and the worker runs it,
retrying failures. With SQLite (native development) there is no queue and no worker: the job runs
in-process right after the commit, and a failure is only logged.

Services defer jobs only through `defer`, never with `task.defer()` directly.
"""

from typing import Any

from django.conf import settings
from django.db import transaction
from procrastinate.exceptions import AlreadyEnqueued
from procrastinate.tasks import Task


def defer[R, **A](task: Task[..., R, A], *, queueing_lock: str | None = None, **kwargs: Any) -> None:
    """Runs `task(**kwargs)` in the background.

    With `queueing_lock` the job is skipped while one with the same lock still waits in the queue.
    Without a queue the lock has no effect.
    """
    if settings.JOB_QUEUE:
        try:
            # A savepoint: a rejected insert must not abort the caller's transaction.
            with transaction.atomic():
                task.configure(queueing_lock=queueing_lock).defer(**kwargs)
        except AlreadyEnqueued:
            pass
    else:
        transaction.on_commit(lambda: task(**kwargs), robust=True)
