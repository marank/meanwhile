"""
Delivers due event reminders once, as the worker does every 30 seconds (core.tasks).
"""

from django.core.management.base import BaseCommand

from core.services.reminders import deliver_due_reminders


class Command(BaseCommand):
    help = "Delivers due event reminders as notifications."

    def handle(self, *args, **options):
        delivered = deliver_due_reminders()
        self.stdout.write(f"{len(delivered)} reminder(s) delivered")
