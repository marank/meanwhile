"""
Delivers due event reminders; run it every minute (cron, systemd timer) so that reminders also go
out while nobody has the app open.
"""

from django.core.management.base import BaseCommand

from core.services.reminders import deliver_due_reminders


class Command(BaseCommand):
    help = "Delivers due event reminders as notifications."

    def handle(self, *args, **options):
        delivered = deliver_due_reminders()
        self.stdout.write(f"{len(delivered)} reminder(s) delivered")
