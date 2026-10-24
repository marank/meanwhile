"""
Jobs of the task queue (core.tasks): emails go out through it, and regular jobs clean up.
"""

from datetime import timedelta

import pytest
from django.core import mail as outbox
from django.utils import timezone

from core.models import DeletedEvent, new_uuid7
from core.services import mail
from core.tasks import clean_up, send_email
from core.tests.helpers import BASE, iso

pytestmark = pytest.mark.django_db


def invite(world, email="guest@example.test"):
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


def test_emails_are_queued_and_sent_by_the_worker(world, settings, task_queue):
    settings.EMAIL_SEND_IN_BACKGROUND = True
    outbox.outbox.clear()  # what setting up the world sent
    invite(world)
    assert len(task_queue.jobs("send_email")) == 1 and outbox.outbox == []

    task_queue.run_jobs()
    [sent] = outbox.outbox
    assert sent.to == ["guest@example.test"]
    # The invitation's iCalendar survives the trip through the queue, inline and as file.
    assert any(mimetype.startswith("text/calendar; method=REQUEST") for _, mimetype in sent.alternatives)
    assert [name for name, _, _ in sent.attachments] == ["invite.ics"]


def test_a_failing_mail_server_fails_the_job_so_that_it_is_tried_again(world, settings, task_queue, monkeypatch):
    settings.EMAIL_SEND_IN_BACKGROUND = True
    invite(world)

    def refused(messages):
        raise ConnectionRefusedError

    monkeypatch.setattr(mail, "deliver", refused)
    with pytest.raises(ConnectionRefusedError):
        task_queue.run_jobs()
    assert send_email.retry_strategy.max_attempts > 1


def test_clean_up_removes_old_records_only(task_queue):
    old = DeletedEvent.objects.create(calendar_id=new_uuid7(), href="old.ics")
    DeletedEvent.objects.filter(pk=old.pk).update(deleted_at=timezone.now() - timedelta(days=91))
    recent = DeletedEvent.objects.create(calendar_id=new_uuid7(), href="recent.ics")
    clean_up(timestamp=0)
    assert list(DeletedEvent.objects.values_list("pk", flat=True)) == [recent.pk]
