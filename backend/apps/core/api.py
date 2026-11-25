"""
Top-level Django Ninja API.

Endpoints need a signed-in user (the session cookie, `django_auth`) unless they say `auth=None`;
with the session comes Ninja's CSRF check.
"""

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext
from ninja import NinjaAPI
from ninja.errors import HttpError
from ninja.security import django_auth

api = NinjaAPI(
    title="Calendar API",
    version="0.0.0",
    auth=django_auth,
    # The interactive docs load their scripts from a CDN, which the CSP allows in DEBUG only.
    docs_url="/docs" if settings.DEBUG else None,
)


@api.exception_handler(HttpError)
def http_error(request: HttpRequest, exc: HttpError) -> HttpResponse:
    # Ninja's default handler calls str(exc), which fails for structured details such as
    # booking conflicts ({"message": ..., "conflicts": [...]}); pass those through as-is.
    # Ninja types the message as str; our own errors pass these structures too.
    message: object = exc.message
    detail = message if isinstance(message, (dict, list)) else str(exc)
    return api.create_response(request, {"detail": detail}, status=exc.status_code)


@api.exception_handler(ObjectDoesNotExist)
def not_found(request: HttpRequest, exc: ObjectDoesNotExist) -> HttpResponse:
    # An id in the path or payload that names nothing, e.g. Calendar.objects.get(id=calendar_id).
    # Every concrete model has its DoesNotExist; the stubs only know it on the models themselves.
    model = next((m for m in apps.get_models() if type(exc) is m.DoesNotExist), None)  # type: ignore[attr-defined]
    name = str(model._meta.verbose_name).capitalize() if model else "Object"
    return api.create_response(request, {"detail": f"{name} not found"}, status=404)


@api.exception_handler(ValidationError)
def malformed_id(request: HttpRequest, exc: ValidationError) -> HttpResponse:
    # An id that isn't even a UUID (Calendar.objects.get(id="nope")) names nothing, like an unknown one.
    return api.create_response(request, {"detail": gettext("Object not found")}, status=404)


@api.exception_handler(IntegrityError)
def conflict(request: HttpRequest, exc: IntegrityError) -> HttpResponse:
    # A unique constraint caught what a view's check let through, e.g. two requests adding the same
    # member at once: the second one learns it is already there.
    return api.create_response(request, {"detail": gettext("This already exists or was just changed")}, status=409)


# Register routers
from apps.core.views import (  # noqa: E402
    admin,
    approvals,
    availability,
    calendars,
    categories,
    comments,
    events,
    groups,
    layout,
    misc,
    notifications,
    resources,
    rsvp,
    search,
    unsubscribe,
    users,
)

api.add_router("", misc.router)
api.add_router("", users.router)
api.add_router("", admin.router)
api.add_router("", groups.router)
api.add_router("", layout.router)
api.add_router("", search.router)
api.add_router("", calendars.router)
api.add_router("", categories.router)
api.add_router("", resources.router)
api.add_router("", events.router)
api.add_router("", comments.router)
api.add_router("", notifications.router)
api.add_router("", approvals.router)
api.add_router("", availability.router)
api.add_router("", rsvp.router)
api.add_router("", unsubscribe.router)
