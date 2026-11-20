from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

import pytest
from procrastinate.contrib.django import app as task_app
from procrastinate.testing import InMemoryConnector
from pytest_django.fixtures import Settings

from apps.core.services import mail
from apps.core.tests.helpers import BASE, Api, Response, TaskQueue, World, iso, make_user


@pytest.fixture(scope="session")
def django_db_modify_db_settings(django_db_modify_db_settings_parallel_suffix: None) -> None:
    """No persistent connections: those of other threads (e.g. the WebSocket consumers') would keep the
    test database from being dropped at the end."""
    from django.conf import settings

    settings.DATABASES["default"]["CONN_MAX_AGE"] = 0


@pytest.fixture(autouse=True)
def own_cache(settings: Settings) -> None:
    """A cache of the test's own (counts of failed logins), not the Redis of the development setup."""
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    from django.core.cache import cache

    cache.clear()


@pytest.fixture(autouse=True)
def task_queue() -> Iterator[TaskQueue]:
    """Jobs (apps.core.tasks) are kept in memory; a test runs them with `task_queue.run_jobs()`."""
    connector = InMemoryConnector()
    with task_app.replace_connector(connector) as app:
        yield TaskQueue(app, connector)


@pytest.fixture(autouse=True)
def send_emails_right_away(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Emails go out at once (tests run inside a transaction that never commits) and in the test's thread."""
    settings.EMAIL_SEND_IN_BACKGROUND = False
    settings.APP_URL = "http://app.test"
    settings.IMIP_ADDRESS = ""
    monkeypatch.setattr(mail, "_after_commit", lambda callback: callback())


@pytest.fixture
def world() -> World:
    """A calendar with members in every role relevant to approvals."""
    users = {
        name: make_user(name)
        for name in (
            "owner",
            "full",
            "booker",
            "other",
            "approver",
            "resapprover",
            "outsider",
        )
    }
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

    def resource(
        name: str, requires_approval: bool = True, approver_ids: list[str] | None = None, **extra: Any
    ) -> dict[str, Any]:
        res = owner.post(
            f"/calendars/{cal['id']}/resources",
            {"name": name, "requires_approval": requires_approval, **extra},
        )
        assert res.status_code == 200, res.content
        created: dict[str, Any] = res.json()
        if approver_ids:
            res = owner.put(f"/calendars/{cal['id']}/resources/{created['id']}/approvers", {"user_ids": approver_ids})
            assert res.status_code == 200, res.content
            created["approvers"] = res.json()
        return created

    def book(api: Api, resource_id: str | None, start: datetime = BASE, hours: int = 1, **extra: Any) -> Response:
        return api.post(
            f"/calendars/{cal['id']}/events",
            {
                "title": extra.pop("title", "Booking"),
                "start": iso(start),
                "end": iso(start + timedelta(hours=hours)),
                "resource_id": resource_id,
                **extra,
            },
        )

    return {"users": users, "api": apis, "cal": cal, "resource": resource, "book": book}
