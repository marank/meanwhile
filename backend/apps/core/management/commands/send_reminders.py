"""
Delivers due event reminders once, as the worker does every 30 seconds (apps.core.tasks).
"""

from typing import Any

from django.core.management.base import BaseCommand

from apps.core.services.reminders import deliver_due_reminders


class Command(BaseCommand):
    help = "Delivers due event reminders as notifications."

    def handle(self, *args: Any, **options: Any) -> None:
        delivered = deliver_due_reminders()
        self.stdout.write(f"{len(delivered)} reminder(s) delivered")
