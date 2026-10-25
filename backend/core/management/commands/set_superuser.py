"""
Makes the user of an email address superuser, or with --revoke takes it away. Superusers may sign
in to the Django admin (/admin/) and do everything there; the app itself doesn't hand this out.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from core.models import User


class Command(BaseCommand):
    help = "Makes the user of an email address superuser (Django admin at /admin/), or with --revoke no longer."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("email", help="Email address of the user")
        parser.add_argument("--revoke", action="store_true", help="Take superuser away instead")

    def handle(self, *args: Any, email: str, revoke: bool, **options: Any) -> None:
        user = User.objects.filter(email__iexact=email.strip()).first()
        if user is None:
            raise CommandError(f"There is no user with the email address {email}.")

        superuser = not revoke
        if user.is_superuser == superuser:
            self.stdout.write(f"{user.email} {'is' if superuser else 'is not'} superuser already.")
            return
        user.is_superuser = superuser
        user.save(update_fields=["is_superuser"])
        self.stdout.write(f"{user.email} {'is superuser now' if superuser else 'is no longer superuser'}.")
