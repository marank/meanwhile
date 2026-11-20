"""
Sessions signed in with Django's ModelBackend name it; it was replaced by apps.core.auth_backends.AppModelBackend,
and Django ends sessions whose backend is no longer configured. They are moved over, so nobody is signed out.
"""

from typing import Any

from django.contrib.auth import BACKEND_SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.db import migrations
from django.utils import timezone

OLD = "django.contrib.auth.backends.ModelBackend"
NEW = "apps.core.auth_backends.AppModelBackend"


def move_sessions(apps: Any, schema_editor: Any, old: str = OLD, new: str = NEW) -> None:
    Session = apps.get_model("sessions", "Session")
    for row in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        store = SessionStore(session_key=row.session_key)
        data = store.decode(row.session_data)
        if data.get(BACKEND_SESSION_KEY) == old:
            data[BACKEND_SESSION_KEY] = new
            row.session_data = store.encode(data)
            row.save(update_fields=["session_data"])


def move_back(apps: Any, schema_editor: Any) -> None:
    move_sessions(apps, schema_editor, old=NEW, new=OLD)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("sessions", "0001_initial"),
    ]

    operations = [migrations.RunPython(move_sessions, move_back)]
