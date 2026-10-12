"""
The user's layout: their folders, and where their calendars sit among them (the sidebar).

    GET    /layout                  folders and calendars, to build the tree in one request
    POST   /layout/folders          create a folder
    PATCH  /layout/folders/{id}     rename or move a folder
    DELETE /layout/folders/{id}     delete a folder (what is in it moves up)
    PATCH  /layout/items            place several folders and calendars at once (drag and drop)
"""

from django.db import transaction
from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import CalendarGroup, CalendarMember, CalendarSubscription, Folder
from core.realtime import broadcast
from core.schemas import (
    FolderCreate,
    FolderOut,
    FolderUpdate,
    LayoutItemsUpdate,
    LayoutOut,
)
from core.views.calendars import list_calendars

router = CSRFRouter()


def _folder_parents(user) -> dict[str, str | None]:
    return {str(id): parent for id, parent in Folder.objects.filter(user=user).values_list("id", "parent_id")}


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


@router.get("/layout", response=LayoutOut, auth=django_auth)
def get_layout(request):
    folders = Folder.objects.filter(user=request.user).order_by("position", "name")
    return {"folders": list(folders), "calendars": list_calendars(request)}


@router.post("/layout/folders", response=FolderOut, auth=django_auth)
def create_folder(request, payload: FolderCreate):
    _require_own_folder(_folder_parents(request.user), payload.parent_id)
    return Folder.objects.create(
        user=request.user, name=payload.name, parent_id=payload.parent_id, position=payload.position
    )


@router.patch("/layout/folders/{folder_id}", response=FolderOut, auth=django_auth)
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


@router.delete("/layout/folders/{folder_id}", auth=django_auth)
def delete_folder(request, folder_id: str):
    Folder.objects.filter(id=folder_id, user=request.user).delete()
    return {"ok": True}


@router.patch("/layout/items", auth=django_auth)
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
        if item.type == "folder":
            Folder.objects.filter(id=item.id, user=user).update(position=item.position, parent_id=item.parent_id)
        else:
            # Calendars are identified by their own id, as everywhere in the app. A membership holds where
            # its calendar sits; without one (a public calendar added, one shared through a group) the
            # user's CalendarSubscription does, made on the first move for a group's calendar.
            place = {"position": item.position, "folder_id": item.parent_id}
            if CalendarMember.objects.filter(calendar_id=item.id, user=user).update(**place):
                continue
            if CalendarSubscription.objects.filter(calendar_id=item.id, user=user).update(**place):
                continue
            if CalendarGroup.objects.filter(calendar_id=item.id, group__in=user.groups.all()).exists():
                CalendarSubscription.objects.create(calendar_id=item.id, user=user, **place)
    # The bulk updates send no signals; the user's other tabs show the new order.
    broadcast.calendars_changed([user.id])
    return {"ok": True}
