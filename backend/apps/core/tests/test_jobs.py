"""
apps.core.jobs.defer: into the task queue with PostgreSQL, in-process after the commit without one.
"""

from collections.abc import Callable
from typing import Any

import pytest
from pytest_django.fixtures import Settings

from apps.core import jobs
from apps.core.models import DeletedEvent, new_uuid7
from apps.core.tasks import clean_up
from apps.core.tests.helpers import TaskQueue

pytestmark = pytest.mark.django_db

Capture = Callable[..., Any]


def test_with_a_queue_the_job_waits_for_the_worker(settings: Settings, task_queue: TaskQueue) -> None:
    settings.JOB_QUEUE = True
    jobs.defer(clean_up, timestamp=0)
    assert [job["args"] for job in task_queue.jobs("clean_up")] == [{"timestamp": 0}]


def test_a_queueing_lock_skips_a_job_while_the_same_one_waits(settings: Settings, task_queue: TaskQueue) -> None:
    settings.JOB_QUEUE = True
    jobs.defer(clean_up, queueing_lock="clean", timestamp=0)
    jobs.defer(clean_up, queueing_lock="clean", timestamp=1)
    assert len(task_queue.jobs("clean_up")) == 1


def test_without_a_queue_the_job_runs_after_the_commit(
    settings: Settings, task_queue: TaskQueue, django_capture_on_commit_callbacks: Capture
) -> None:
    settings.JOB_QUEUE = False
    calls: list[int] = []

    class Spy:
        def __call__(self, **kwargs: int) -> None:
            calls.append(kwargs["timestamp"])

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        jobs.defer(Spy(), timestamp=7)  # type: ignore[arg-type]  # stands in for a task
        assert calls == []  # not before the commit
    assert len(callbacks) == 1 and calls == [7]
    assert task_queue.jobs("") == []


def test_without_a_queue_a_failing_job_does_not_fail_the_request(
    settings: Settings, django_capture_on_commit_callbacks: Capture
) -> None:
    settings.JOB_QUEUE = False

    def fails(**kwargs: Any) -> None:
        raise RuntimeError("boom")

    DeletedEvent.objects.create(calendar_id=new_uuid7(), href="kept.ics")
    with django_capture_on_commit_callbacks(execute=True):
        jobs.defer(fails)  # type: ignore[arg-type]  # stands in for a task
    # Django logs the error (robust on_commit callback); the change stays.
    assert DeletedEvent.objects.filter(href="kept.ics").exists()
