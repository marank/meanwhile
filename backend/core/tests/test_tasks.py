"""
Jobs of the task queue (core.tasks): emails go out through it, and regular jobs clean up.
"""

import json
import logging
from datetime import timedelta

import pytest
from django.core import mail as outbox
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from procrastinate import RetryStrategy
from procrastinate.jobs import Job
from pytest_django.fixtures import Settings

from core.log_filters import HideJobArguments
from core.models import DeletedEvent, new_uuid7
from core.services import mail
from core.tasks import clean_up, send_email
from core.tests.helpers import BASE, TaskQueue, World, iso

pytestmark = pytest.mark.django_db


def invite(world: World, email: str = "guest@example.test") -> None:
    owner = world["api"]["owner"]
    event = owner.post(
        f"/calendars/{world['cal']['id']}/events",
        {
            "title": "Planning",
            "start": iso(BASE),
            "end": iso(BASE + timedelta(hours=1)),
        },
    ).json()
    assert owner.post(f"/events/{event['id']}/participants", {"email": email}).status_code == 200


def test_emails_are_queued_and_sent_by_the_worker(world: World, settings: Settings, task_queue: TaskQueue) -> None:
    settings.EMAIL_SEND_IN_BACKGROUND = True
    outbox.outbox.clear()  # what setting up the world sent
    invite(world)
    assert len(task_queue.jobs("send_email")) == 1 and outbox.outbox == []

    task_queue.run_jobs()
    [sent] = outbox.outbox
    assert isinstance(sent, EmailMultiAlternatives)
    assert sent.to == ["guest@example.test"]
    # The invitation's iCalendar survives the trip through the queue, inline and as file.
    assert any(mimetype.startswith("text/calendar; method=REQUEST") for _, mimetype in sent.alternatives)
    assert [name for name, _, _ in sent.attachments] == ["invite.ics"]


def test_a_failing_mail_server_fails_the_job_so_that_it_is_tried_again(
    world: World, settings: Settings, task_queue: TaskQueue, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.EMAIL_SEND_IN_BACKGROUND = True
    invite(world)

    def refused(messages: list[EmailMultiAlternatives]) -> None:
        raise ConnectionRefusedError

    monkeypatch.setattr(mail, "deliver", refused)
    with pytest.raises(ConnectionRefusedError):
        task_queue.run_jobs()
    retry_strategy = send_email.retry_strategy
    assert isinstance(retry_strategy, RetryStrategy) and retry_strategy.max_attempts is not None
    assert retry_strategy.max_attempts > 1


def test_clean_up_removes_old_records_only(task_queue: TaskQueue) -> None:
    old = DeletedEvent.objects.create(calendar_id=new_uuid7(), href="old.ics")
    DeletedEvent.objects.filter(pk=old.pk).update(deleted_at=timezone.now() - timedelta(days=91))
    recent = DeletedEvent.objects.create(calendar_id=new_uuid7(), href="recent.ics")
    clean_up(timestamp=0)
    assert list(DeletedEvent.objects.values_list("pk", flat=True)) == [recent.pk]


def test_the_log_names_jobs_without_their_arguments() -> None:
    # An email's addresses and RSVP links stay out of the log.
    job = Job(
        id=35,
        queue="mail",
        lock=None,
        queueing_lock=None,
        task_name="core.tasks.send_email",
        task_kwargs={"message": {"to": ["guest@example.test"], "body": "/rsvp/secret-token"}},
    )
    record = logging.makeLogRecord(
        {"name": "procrastinate.worker", "msg": f"Job {job.call_string} ended", "job": job.log_context()}
    )
    console = next(
        handler
        for handler in logging.getLogger().handlers
        if any(isinstance(f, HideJobArguments) for f in handler.filters)
    )
    assert console.filter(record)
    assert record.getMessage() == "Job core.tasks.send_email[35] ended"
    assert "secret-token" not in str(record.__dict__)


def test_queued_emails_keep_the_logo_they_carry(task_queue: TaskQueue, settings: Settings) -> None:
    settings.EMAIL_SEND_IN_BACKGROUND = True
    outbox.outbox.clear()
    mail.send([mail.build_message("ann@example.test", "Hello", ["Hi"], "en")])
    [job] = task_queue.jobs("send_email")
    json.dumps(job["args"])  # saved as JSON
    task_queue.run_jobs()
    [sent] = outbox.outbox
    images = [p for p in sent.message().walk() if p.get("Content-ID") == "<logo@meanwhile>"]
    assert len(images) == 1 and images[0].get_content_type() == "image/png"
