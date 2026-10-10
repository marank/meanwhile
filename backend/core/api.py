"""
Top-level Django Ninja API.

CSRF protection is handled automatically by the `django_auth` session-cookie
authentication class used on all protected endpoints.
"""

from ninja import NinjaAPI, Router
from ninja.errors import HttpError


CSRFRouter = Router

api = NinjaAPI(
    title="Calendar API",
    version="0.1.0",
)


@api.exception_handler(HttpError)
def http_error(request, exc: HttpError):
    # Ninja's default handler calls str(exc), which fails for structured details such as
    # booking conflicts ({"message": ..., "conflicts": [...]}); pass those through as-is.
    detail = exc.message if isinstance(exc.message, (dict, list)) else str(exc)
    return api.create_response(request, {"detail": detail}, status=exc.status_code)

# Register routers
from core.views import (  # noqa: E402
    admin,
    approvals,
    calendars,
    categories,
    comments,
    events,
    folders,
    groups,
    misc,
    notifications,
    resources,
    search,
    sidebar,
    users,
)

api.add_router("", misc.router)
api.add_router("", users.router)
api.add_router("", admin.router)
api.add_router("", groups.router)
api.add_router("", folders.router)
api.add_router("", sidebar.router)
api.add_router("", search.router)
api.add_router("", calendars.router)
api.add_router("", categories.router)
api.add_router("", resources.router)
api.add_router("", events.router)
api.add_router("", comments.router)
api.add_router("", notifications.router)
api.add_router("", approvals.router)
