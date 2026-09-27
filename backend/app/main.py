from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from a2wsgi import WSGIMiddleware

from app.api import (
    admin,
    approvals,
    auth,
    calendars,
    categories,
    events,
    feed,
    folders,
    resources,
    sidebar,
    users,
)
from app.config import settings
from app.database import get_db
from app.models import get_or_create_app_settings
from app.schemas import AppSettingsOut

app = FastAPI(title="Calendar API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(calendars.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(folders.router, prefix="/api")
app.include_router(sidebar.router, prefix="/api")
app.include_router(resources.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(approvals.router, prefix="/api")
app.include_router(feed.router, prefix="/ics")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/settings", response_model=AppSettingsOut)
def public_app_settings(db: Session = Depends(get_db)) -> AppSettingsOut:
    return get_or_create_app_settings(db)


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
