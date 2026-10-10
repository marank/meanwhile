"""
Sidebar folder endpoints.
"""

from ninja import Router
from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import Folder
from core.schemas import FolderCreate, FolderOut, FolderUpdate

router = CSRFRouter()


def _serialize_folder(folder: Folder) -> dict:
    return {
        "id": folder.id,
        "name": folder.name,
        "parent_id": str(folder.parent_id) if folder.parent_id else None,
        "position": folder.position,
    }


def _detect_cycle(folder: Folder, parent_id: str | None) -> bool:
    if parent_id is None:
        return False
    if str(folder.id) == str(parent_id):
        return True
    current = Folder.objects.filter(id=parent_id).first()
    seen = set()
    while current:
        if str(current.id) == str(folder.id):
            return True
        if str(current.id) in seen:
            break
        seen.add(str(current.id))
        current = current.parent
    return False


@router.get("/folders", response=list[FolderOut], auth=django_auth)
def list_folders(request):
    return Folder.objects.filter(user=request.user).order_by("position", "name")


@router.post("/folders", response=FolderOut, auth=django_auth)
def create_folder(request, payload: FolderCreate):
    if payload.parent_id and _detect_cycle(None, payload.parent_id):
        raise HttpError(400, "Invalid parent folder")
    folder = Folder.objects.create(
        user=request.user,
        name=payload.name,
        parent_id=payload.parent_id,
        position=payload.position,
    )
    return _serialize_folder(folder)


@router.patch("/folders/{folder_id}", response=FolderOut, auth=django_auth)
def update_folder(request, folder_id: str, payload: FolderUpdate):
    folder = Folder.objects.get(id=folder_id, user=request.user)
    data = payload.dict(exclude_unset=True)
    new_parent = data.get("parent_id")
    if new_parent is not None and _detect_cycle(folder, new_parent):
        raise HttpError(400, "Folder cycle detected")
    for attr, value in data.items():
        setattr(folder, attr, value)
    folder.save()
    return _serialize_folder(folder)


@router.delete("/folders/{folder_id}", auth=django_auth)
def delete_folder(request, folder_id: str):
    Folder.objects.filter(id=folder_id, user=request.user).delete()
    return {"ok": True}
