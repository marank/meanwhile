"""
The user's layout: their folders, and where their calendars sit among them (the sidebar).

    GET    /layout                  folders and calendars, to build the tree in one request
    POST   /layout/folders          create a folder
    PATCH  /layout/folders/{id}     rename or move a folder
    DELETE /layout/folders/{id}     delete a folder (what is in it moves up)
    PATCH  /layout/items            place several folders and calendars at once (drag and drop)
"""

from typing import Any

from ninja import Router

from apps.core.models import Folder
from apps.core.schemas import (
    FolderCreate,
    FolderOut,
    FolderUpdate,
    LayoutItemsUpdate,
    LayoutOut,
    OkOut,
)
from apps.core.services import layout
from apps.core.views.calendars import sidebar_calendars_of
from apps.core.views.common import AuthedRequest

router = Router()


@router.get("/layout", response=LayoutOut)
def get_layout(request: AuthedRequest) -> dict[str, Any]:
    folders = Folder.objects.filter(user=request.user).order_by("position", "name")
    return {"folders": list(folders), "calendars": sidebar_calendars_of(request.user)}


@router.post("/layout/folders", response=FolderOut)
def create_folder(request: AuthedRequest, payload: FolderCreate) -> Folder:
    return layout.create_folder(request.user, payload)


@router.patch("/layout/folders/{folder_id}", response=FolderOut)
def update_folder(request: AuthedRequest, folder_id: str, payload: FolderUpdate) -> Folder:
    return layout.update_folder(request.user, folder_id, payload.dict(exclude_unset=True))


@router.delete("/layout/folders/{folder_id}", response=OkOut)
def delete_folder(request: AuthedRequest, folder_id: str) -> dict[str, bool]:
    Folder.objects.filter(id=folder_id, user=request.user).delete()
    return {"ok": True}


@router.patch("/layout/items", response=OkOut)
def update_layout_items(request: AuthedRequest, payload: LayoutItemsUpdate) -> dict[str, bool]:
    """Sets parent folder and position of folders and calendars; ones that are gone meanwhile are skipped."""
    layout.place_items(request.user, payload)
    return {"ok": True}
