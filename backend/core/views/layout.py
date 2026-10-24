"""
The user's layout: their folders, and where their calendars sit among them (the sidebar).

    GET    /layout                  folders and calendars, to build the tree in one request
    POST   /layout/folders          create a folder
    PATCH  /layout/folders/{id}     rename or move a folder
    DELETE /layout/folders/{id}     delete a folder (what is in it moves up)
    PATCH  /layout/items            place several folders and calendars at once (drag and drop)
"""

from django.db import transaction
from ninja import Router
from ninja.errors import HttpError

from core.models import CalendarMember, Folder, as_uuid
from core.realtime import broadcast
from core.schemas import (
    FolderCreate,
    FolderOut,
    FolderUpdate,
    LayoutItemsUpdate,
    LayoutOut,
)
from core.views.calendars import sidebar_calendars_of

router = Router()


def _folder_parents(user) -> dict[str, str | None]:
    """Each of the user's folders' parent, by id; ids as strings, as requests name them."""
    rows = Folder.objects.filter(user=user).values_list("id", "parent_id")
    return {str(id): str(parent) if parent else None for id, parent in rows}


def _require_own_folder(parents: dict[str, str | None], folder_id: str | None) -> None:
    if folder_id is not None and folder_id not in parents:
        raise HttpError(404, "Folder not found")


def _has_cycle(parents: dict[str, str | None]) -> bool:
    for start in parents:
        seen = {start}
        current = parents[start]
        while current is not None:
            if current in seen:
                return True
            seen.add(current)
            current = parents.get(current)
    return False


@router.get("/layout", response=LayoutOut)
def get_layout(request):
    folders = Folder.objects.filter(user=request.user).order_by("position", "name")
    return {"folders": list(folders), "calendars": sidebar_calendars_of(request.user)}


@router.post("/layout/folders", response=FolderOut)
def create_folder(request, payload: FolderCreate):
    _require_own_folder(_folder_parents(request.user), payload.parent_id)
    return Folder.objects.create(
        user=request.user, name=payload.name, parent_id=payload.parent_id, position=payload.position
    )


@router.patch("/layout/folders/{folder_id}", response=FolderOut)
def update_folder(request, folder_id: str, payload: FolderUpdate):
    folder = Folder.objects.get(id=folder_id, user=request.user)
    data = payload.dict(exclude_unset=True)
    if "parent_id" in data:
        parents = _folder_parents(request.user)
        _require_own_folder(parents, data["parent_id"])
        parents[str(folder.id)] = data["parent_id"]
        if _has_cycle(parents):
            raise HttpError(400, "A folder cannot be moved into itself")
    for attr, value in data.items():
        setattr(folder, attr, value)
    folder.save()
    return folder


@router.delete("/layout/folders/{folder_id}")
def delete_folder(request, folder_id: str):
    Folder.objects.filter(id=folder_id, user=request.user).delete()
    return {"ok": True}


@router.patch("/layout/items")
@transaction.atomic
def update_layout_items(request, payload: LayoutItemsUpdate):
    """Sets parent folder and position of folders and calendars; ones that are gone meanwhile are skipped."""
    user = request.user
    parents = _folder_parents(user)
    for item in payload.items:
        _require_own_folder(parents, item.parent_id)
    for item in payload.items:
        if item.type == "folder" and item.id in parents:
            parents[item.id] = item.parent_id
    if _has_cycle(parents):
        raise HttpError(400, "A folder cannot be moved into itself")
    for item in payload.items:
        if as_uuid(item.id) is None:
            continue  # names nothing, like an item that is gone
        if item.type == "folder":
            Folder.objects.filter(id=item.id, user=user).update(position=item.position, parent_id=item.parent_id)
        else:
            # Calendars are identified by their own id, as everywhere in the app; the user's membership of
            # one (granted, from a group or added) holds where it sits.
            CalendarMember.objects.filter(calendar_id=item.id, user=user).update(
                position=item.position, folder_id=item.parent_id
            )
    # The bulk updates send no signals; the user's other tabs show the new order.
    broadcast.calendars_changed([user.id])
    return {"ok": True}
