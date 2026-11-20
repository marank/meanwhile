"""
What lasts for one CalDAV request.

Radicale asks the plugins the same questions many times per request (e.g. the rights of every item
it lists), so their answers are kept for the request.
"""

import contextlib
from collections.abc import Callable, Iterator
from contextvars import ContextVar
from typing import Any, cast

from django.db import close_old_connections

_answers: ContextVar[dict[tuple[object, ...], Any] | None] = ContextVar("caldav_request_answers", default=None)


@contextlib.contextmanager
def request_scope() -> Iterator[None]:
    """One request; its database connection is tidied up as Django does around its own requests."""
    close_old_connections()
    token = _answers.set({})
    try:
        yield
    finally:
        _answers.reset(token)
        close_old_connections()


def once_per_request[T](key: tuple[object, ...], compute: Callable[[], T]) -> T:
    """`compute()`, remembered under `key` until the request ends (outside a request: not at all)."""
    answers = _answers.get()
    if answers is None:
        return compute()
    if key not in answers:
        answers[key] = compute()
    return cast(T, answers[key])
