"""
Attachment endpoints: files and links on events, and downloading files.
"""

from typing import Any

from django.db import transaction
from django.http import FileResponse, HttpRequest
from django.utils.translation import gettext
from ninja import File, Router, UploadedFile
from ninja.errors import HttpError

from apps.core.models import AttachmentKind, Event, EventAttachment, User
from apps.core.schemas import AttachmentLinkCreate, AttachmentOut, OkOut
from apps.core.services import attachments
from apps.core.services.permissions import can_modify_event, get_visible_event
from apps.core.views.common import AuthedRequest

router = Router()


def _serialize(attachment: EventAttachment) -> dict[str, Any]:
    return {
        "id": attachment.id,
        "kind": attachment.kind,
        "name": attachment.name,
        "url": attachment.url if attachment.kind == AttachmentKind.LINK else attachments.download_path(attachment),
        "content_type": attachment.content_type,
        "size": attachment.size,
        "added_by_name": attachment.added_by.display_name if attachment.added_by else None,
        "created_at": attachment.created_at,
    }


def _editable_event(event_id: str, user: User) -> Event:
    # Who sees the event learns it is there before being told they may not change it.
    event, membership = get_visible_event(event_id, user)
    if not can_modify_event(event, str(user.id), membership.role):
        raise HttpError(403, gettext("You do not have permission to edit this event"))
    return event


@router.get("/events/{event_id}/attachments", response=list[AttachmentOut])
def list_attachments(request: AuthedRequest, event_id: str) -> list[dict[str, Any]]:
    event, _ = get_visible_event(event_id, request.user)
    return [_serialize(a) for a in attachments.attachments_of(event)]


@router.post("/events/{event_id}/attachments/files", response=AttachmentOut)
def add_file(request: AuthedRequest, event_id: str, file: File[UploadedFile]) -> dict[str, Any]:
    event = _editable_event(event_id, request.user)
    with transaction.atomic():
        return _serialize(attachments.add_file(event, request.user, file))


@router.post("/events/{event_id}/attachments/links", response=AttachmentOut)
def add_link(request: AuthedRequest, event_id: str, payload: AttachmentLinkCreate) -> dict[str, Any]:
    event = _editable_event(event_id, request.user)
    with transaction.atomic():
        return _serialize(attachments.add_link(event, request.user, payload.url, payload.name))


@router.delete("/events/{event_id}/attachments/{attachment_id}", response=OkOut)
def remove_attachment(request: AuthedRequest, event_id: str, attachment_id: str) -> dict[str, bool]:
    event = _editable_event(event_id, request.user)
    attachment = EventAttachment.objects.get(id=attachment_id, event=attachments.series_of(event))
    with transaction.atomic():
        attachments.remove(attachment, request.user)
    return {"ok": True}


@router.get("/attachments/{attachment_id}/download")
def download(request: HttpRequest, attachment_id: str) -> FileResponse:
    """A file attachment's content, for everyone who may see its event; always as a download."""
    user = request.user
    assert isinstance(user, User)  # django_auth lets only signed-in users through
    attachment = EventAttachment.objects.select_related("event").get(id=attachment_id, kind=AttachmentKind.FILE)
    get_visible_event(str(attachment.event_id), user)
    path = attachments.file_path(attachment)
    if not path.is_file():
        raise HttpError(404, gettext("The file is no longer there"))
    response = FileResponse(
        path.open("rb"), as_attachment=True, filename=attachment.name, content_type=attachment.content_type
    )
    # Never shown as a page of the app's origin, whatever a browser makes of the content.
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-cache"
    return response
