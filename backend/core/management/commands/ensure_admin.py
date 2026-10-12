"""
Creates or updates the admin of ADMIN_EMAIL, with ADMIN_PASSWORD and ADMIN_NAME; run on every
start of the containers, after the migrations.

Without ADMIN_EMAIL nothing happens. An existing user of that address becomes admin; their
password is only replaced when ADMIN_PASSWORD differs from it (setting it again would sign them
out everywhere). A new user needs ADMIN_PASSWORD.
"""

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import User


class Command(BaseCommand):
    help = "Creates or updates the admin user from ADMIN_EMAIL, ADMIN_PASSWORD and ADMIN_NAME."

    @transaction.atomic
    def handle(self, *args, **options):
        email = settings.ADMIN_EMAIL.strip().lower()
        password = settings.ADMIN_PASSWORD
        name = settings.ADMIN_NAME.strip()
        if not email:
            self.stdout.write("ADMIN_EMAIL is not set; no admin user to set up.")
            return

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            if not password:
                raise CommandError(f"ADMIN_PASSWORD is needed to create the admin user {email}.")
            user = User.objects.create_superuser(email=email, password=password, display_name=name or email)
            EmailAddress.objects.create(user=user, email=email, primary=True, verified=True)
            self.stdout.write(f"Admin user {email} created.")
            return

        changed = []
        if not (user.is_admin and user.is_superuser and user.is_active):
            user.is_admin = user.is_superuser = user.is_active = True
            changed.append("admin rights")
        if password and not user.check_password(password):
            user.set_password(password)
            changed.append("password")
        if name and user.display_name != name:
            user.display_name = name
            changed.append("name")
        if changed:
            user.save()
            self.stdout.write(f"Admin user {email} updated: {', '.join(changed)}.")
        else:
            self.stdout.write(f"Admin user {email} is up to date.")
