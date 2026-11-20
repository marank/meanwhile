"""
Helpers for tests driven through the HTTP API.
"""

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, TypedDict

from django.test import Client
from procrastinate import App
from procrastinate.testing import InMemoryConnector

from apps.core.models import User

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

type Response = _MonkeyPatchedWSGIResponse  # what the test client returns, per django-stubs

BASE = datetime(2030, 1, 7, 9, 0, tzinfo=UTC)  # a Monday


def iso(dt: datetime) -> str:
    return dt.isoformat()


class Api:
    """Session-authenticated JSON client for one user."""

    def __init__(self, user: User) -> None:
        self.client = Client()
        self.client.force_login(user)
        self.user = user

    def _call(self, method: str, url: str, data: Any = None) -> Response:
        kwargs = {"content_type": "application/json"}
        if data is not None:
            kwargs["data"] = json.dumps(data, default=str)  # model ids are UUIDs
        response: Response = getattr(self.client, method)(f"/api{url}", **kwargs)
        return response

    def get(self, url: str) -> Response:
        return self._call("get", url)

    def post(self, url: str, data: Any = None) -> Response:
        return self._call("post", url, data if data is not None else {})

    def patch(self, url: str, data: Any) -> Response:
        return self._call("patch", url, data)

    def put(self, url: str, data: Any) -> Response:
        return self._call("put", url, data)

    def delete(self, url: str) -> Response:
        return self._call("delete", url)


class TaskQueue:
    def __init__(self, app: App, connector: InMemoryConnector) -> None:
        self.app, self.connector = app, connector

    def jobs(self, task_name: str) -> list[dict[str, Any]]:
        return [job for job in self.connector.jobs.values() if job["task_name"].endswith(task_name)]

    def run_jobs(self) -> None:
        """Runs the waiting jobs here, in the test's transaction (a worker would use threads of its own)."""
        for job in list(self.connector.jobs.values()):
            if job["status"] == "todo":
                self.app.tasks[job["task_name"]](**job["args"])
                job["status"] = "succeeded"


def make_user(name: str) -> User:
    return User.objects.create_user(email=f"{name}@example.test", password="x", display_name=name.title())


class ResourceFactory(Protocol):
    def __call__(
        self, name: str, requires_approval: bool = True, approver_ids: list[str] | None = None, **extra: Any
    ) -> dict[str, Any]: ...


class Booker(Protocol):
    def __call__(
        self, api: Api, resource_id: str | None, start: datetime = BASE, hours: int = 1, **extra: Any
    ) -> Response: ...


class World(TypedDict):
    """What the `world` fixture returns."""

    users: dict[str, User]
    api: dict[str, Api]
    cal: dict[str, Any]
    resource: ResourceFactory
    book: Booker


def add_approver(world: World, path: str, name: str) -> Response:
    """Adds a user to the approvers at `path`, keeping the others (the API sets the whole list)."""
    owner = world["api"]["owner"]
    current = [a["user_id"] for a in owner.get(path).json()]
    return owner.put(path, {"user_ids": [*current, str(world["users"][name].id)]})


def add_default_approver(world: World, name: str) -> None:
    res = add_approver(world, f"/calendars/{world['cal']['id']}/approvers", name)
    assert res.status_code == 200, res.content
