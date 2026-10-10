"""
Sidebar reorder endpoint (folders + calendar memberships).
"""

from ninja import Router
from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import CalendarMember, Folder
from core.schemas import SidebarReorderRequest

router = CSRFRouter()


@router.post("/sidebar/reorder", auth=django_auth)
def reorder_sidebar(request, payload: SidebarReorderRequest):
    user = request.user
    for item in payload.items:
        if item.type == "folder":
            Folder.objects.filter(id=item.id, user=user).update(
                position=item.position,
                parent_id=item.parent_id,
            )
        elif item.type == "calendar":
            CalendarMember.objects.filter(id=item.id, user=user).update(
                position=item.position,
                folder_id=item.parent_id,
            )
        else:
            raise HttpError(400, f"Unknown sidebar item type: {item.type}")
    return {"ok": True}
