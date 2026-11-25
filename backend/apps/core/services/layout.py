"""
The user's layout: their folders, and where their calendars sit among them (the sidebar).
"""

from typing import Any

from django.db import transaction
from django.utils.translation import gettext
from ninja.errors import HttpError

from apps.core.models import CalendarMember, Folder, User, as_uuid
from apps.core.realtime import broadcast
from apps.core.schemas import FolderCreate, LayoutItemsUpdate


def _folder_parents(user: User) -> dict[str, str | None]:
    """Each of the user's folders' parent, by id; ids as strings, as requests name them."""
    folders = Folder.objects.filter(user=user).only("id", "parent_id")
    return {str(folder.id): str(folder.parent_id) if folder.parent_id else None for folder in folders}


def _require_own_folder(parents: dict[str, str | None], folder_id: str | None) -> None:
    if folder_id is not None and folder_id not in parents:
        raise HttpError(404, gettext("Folder not found"))


def _require_no_cycle(parents: dict[str, str | None]) -> None:
    for start in parents:
        seen = {start}
        current = parents[start]
        while current is not None:
            if current in seen:
                raise HttpError(400, gettext("A folder cannot be moved into itself"))
            seen.add(current)
            current = parents.get(current)


def create_folder(user: User, data: FolderCreate) -> Folder:
    _require_own_folder(_folder_parents(user), data.parent_id)
    return Folder.objects.create(user=user, name=data.name, parent_id=data.parent_id, position=data.position)


def update_folder(user: User, folder_id: str, data: dict[str, Any]) -> Folder:
    """Renames or moves the folder, as `data` (the PATCH's set fields) says."""
    folder = Folder.objects.get(id=folder_id, user=user)
    if "parent_id" in data:
        parents = _folder_parents(user)
        _require_own_folder(parents, data["parent_id"])
        parents[str(folder.id)] = data["parent_id"]
        _require_no_cycle(parents)
    for attr, value in data.items():
        setattr(folder, attr, value)
    folder.save()
    return folder


@transaction.atomic
def place_items(user: User, data: LayoutItemsUpdate) -> None:
    """Sets parent folder and position of folders and calendars; ones that are gone meanwhile are skipped."""
    parents = _folder_parents(user)
    for item in data.items:
        _require_own_folder(parents, item.parent_id)
    for item in data.items:
        if item.type == "folder" and item.id in parents:
            parents[item.id] = item.parent_id
    _require_no_cycle(parents)
    for item in data.items:
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
