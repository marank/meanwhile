from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from a2wsgi import WSGIMiddleware

from app.api import (
    approvals,
    auth,
    calendars,
    categories,
    events,
    feed,
    folders,
    resources,
    users,
)
from app.config import settings

app = FastAPI(title="Calendar API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(calendars.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(folders.router, prefix="/api")
app.include_router(resources.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(approvals.router, prefix="/api")
app.include_router(feed.router, prefix="/ics")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Embedded CalDAV server (Radicale)
# ---------------------------------------------------------------------------

from radicale.app import Application as RadicaleApplication
from radicale.config import load as load_radicale_config

_radicale_config = load_radicale_config()
_radicale_config.update(
    {
        "auth": {"type": "app.services.caldav.auth"},
        "rights": {"type": "app.services.caldav.rights"},
        "storage": {"type": "app.services.caldav.storage"},
    },
    source="calendar-app-inline",
)

radicale_app = RadicaleApplication(_radicale_config)
app.mount(settings.caldav_path, WSGIMiddleware(radicale_app))
