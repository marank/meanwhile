"""
Jobs of the task queue (procrastinate), run by `manage.py procrastinate worker`.

Jobs are saved in the database along with the changes that call for them, so none is lost when a
request or the worker stops. Regular jobs are deferred by the worker itself, once each however
many workers run.
"""

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone
from procrastinate import JobContext, RetryStrategy, builtin_tasks
from procrastinate.contrib.django import app

from core.models import DeletedEvent, ReminderDelivery
from core.services import mail
from core.services.itip import fetch_mailbox
from core.services.reminders import DELIVERY_RETENTION, deliver_due_reminders
from core.signals import DELETED_EVENT_RETENTION

logger = logging.getLogger(__name__)

# How long finished jobs stay visible (e.g. in the admin); failed ones a while longer.
FINISHED_JOB_RETENTION = timedelta(days=7)
FAILED_JOB_RETENTION = timedelta(days=30)


# While the mail server is down, tried again after 2, 4, 8, ... seconds, 12 times: for about two hours.
@app.task(queue="mail", retry=RetryStrategy(max_attempts=12, exponential_wait=2))
def send_email(message: dict[str, Any]) -> None:
    """One email (core.services.mail.message_data)."""
    mail.deliver([mail.message_from_data(message)])


@app.periodic(cron="* * * * * */30")
@app.task(queueing_lock="deliver_reminders")
def deliver_reminders(timestamp: int) -> None:
    deliver_due_reminders()


@app.periodic(cron="*/5 * * * *")
@app.task(queueing_lock="fetch_imip_answers")
def fetch_imip_answers(timestamp: int) -> None:
    """Participants' answers from the iMIP mailbox, if there is one (see README)."""
    if not settings.IMIP_IMAP_HOST:
        return
    for line in fetch_mailbox():
        logger.info("iMIP: %s", line)


@app.periodic(cron="17 3 * * *")
@app.task(queueing_lock="clean_up")
def clean_up(timestamp: int) -> None:
    """Records that are only kept for a while."""
    now = timezone.now()
    DeletedEvent.objects.filter(deleted_at__lt=now - DELETED_EVENT_RETENTION).delete()
    ReminderDelivery.objects.filter(occurrence_start__lt=now - DELIVERY_RETENTION).delete()


@app.periodic(cron="47 3 * * *")
@app.task(queueing_lock="remove_old_jobs", pass_context=True)
async def remove_old_jobs(context: JobContext, timestamp: int) -> None:
    await builtin_tasks.remove_old_jobs(
        context, max_hours=int(FINISHED_JOB_RETENTION.total_seconds() // 3600), remove_cancelled=True
    )
    await builtin_tasks.remove_old_jobs(
        context, max_hours=int(FAILED_JOB_RETENTION.total_seconds() // 3600), remove_failed=True
    )
