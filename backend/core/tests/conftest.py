from datetime import datetime, timedelta

import pytest
from procrastinate.contrib.django import app as task_app
from procrastinate.testing import InMemoryConnector

from core.services import mail
from core.tests.helpers import BASE, Api, iso, make_user


@pytest.fixture(scope="session")
def django_db_modify_db_settings(django_db_modify_db_settings_parallel_suffix):
    """No persistent connections: those of other threads (e.g. the WebSocket consumers') would keep the
    test database from being dropped at the end."""
    from django.conf import settings

    settings.DATABASES["default"]["CONN_MAX_AGE"] = 0


@pytest.fixture(autouse=True)
def own_cache(settings):
    """A cache of the test's own (counts of failed logins), not the Redis of the development setup."""
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    from django.core.cache import cache

    cache.clear()


@pytest.fixture(autouse=True)
def task_queue():
    """Jobs (core.tasks) are kept in memory; a test runs them with `task_queue.run_jobs()`."""
    connector = InMemoryConnector()
    with task_app.replace_connector(connector) as app:
        yield TaskQueue(app, connector)


class TaskQueue:
    def __init__(self, app, connector: InMemoryConnector):
        self.app, self.connector = app, connector

    def jobs(self, task_name: str) -> list[dict]:
        return [job for job in self.connector.jobs.values() if job["task_name"].endswith(task_name)]

    def run_jobs(self) -> None:
        """Runs the waiting jobs here, in the test's transaction (a worker would use threads of its own)."""
        for job in list(self.connector.jobs.values()):
            if job["status"] == "todo":
                self.app.tasks[job["task_name"]](**job["args"])
                job["status"] = "succeeded"


@pytest.fixture(autouse=True)
def send_emails_right_away(settings, monkeypatch):
    """Emails go out at once (tests run inside a transaction that never commits) and in the test's thread."""
    settings.EMAIL_SEND_IN_BACKGROUND = False
    settings.APP_URL = "http://app.test"
    settings.IMIP_ADDRESS = ""
    monkeypatch.setattr(mail, "_after_commit", lambda callback: callback())


@pytest.fixture
def world():
    """A calendar with members in every role relevant to approvals."""
    users = {name: make_user(name) for name in (
        "owner", "full", "booker", "other", "approver", "resapprover", "outsider",
    )}
    apis = {name: Api(user) for name, user in users.items()}
    owner = apis["owner"]

    cal = owner.post("/calendars", {"name": "Team"}).json()
    for name, role in (
        ("full", "full"),
        ("booker", "own"),
        ("other", "own"),
        ("approver", "own"),
        ("resapprover", "own"),
    ):
        res = owner.post(f"/calendars/{cal['id']}/members", {"user_id": str(users[name].id), "role": role})
        assert res.status_code == 200, res.content

    def resource(name: str, requires_approval: bool = True, approver_ids: list[str] | None = None, **extra):
        res = owner.post(
            f"/calendars/{cal['id']}/resources",
            {"name": name, "requires_approval": requires_approval, **extra},
        )
        assert res.status_code == 200, res.content
        created = res.json()
        if approver_ids:
            res = owner.put(f"/calendars/{cal['id']}/resources/{created['id']}/approvers", {"user_ids": approver_ids})
            assert res.status_code == 200, res.content
            created["approvers"] = res.json()
        return created

    def book(api: Api, resource_id: str | None, start: datetime = BASE, hours: int = 1, **extra):
        return api.post(f"/calendars/{cal['id']}/events", {
            "title": extra.pop("title", "Booking"),
            "start": iso(start),
            "end": iso(start + timedelta(hours=hours)),
            "resource_id": resource_id,
            **extra,
        })

    return {"users": users, "api": apis, "cal": cal, "resource": resource, "book": book}
