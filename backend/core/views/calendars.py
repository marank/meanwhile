"""
Calendar, membership, feed and group-link endpoints.
"""

import secrets

from django.db import IntegrityError, transaction
from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import (
    Calendar,
    CalendarApprover,
    CalendarGroup,
    CalendarMember,
    User,
    UserGroup,
)
from core.models import ResourceApprover
from core.models.base import Role
from core.models.calendar_colors import COLOR_FIELDS
from core.schemas import (
    ApproverOut,
    ApproversIn,
    CalendarCreate,
    CalendarGroupLinkCreate,
    CalendarGroupLinkOut,
    CalendarGroupLinkUpdate,
    CalendarListOut,
    CalendarMemberCreate,
    CalendarMemberOut,
    CalendarMemberUpdate,
    CalendarOut,
    CalendarUpdate,
    FeedTokenRotateOut,
    FeedUrlOut,
)
from core.services.calendars import create_calendar as create_calendar_for
from core.services.notifications import notify
from core.services.permissions import (
    get_direct_membership,
    get_membership,
    is_owner,
    role_weight,
)
from core.views.common import approvers_of, replace_approvers

router = CSRFRouter()


def _make_feed_url(request, token: str) -> str:
    from django.conf import settings as django_settings

    base = (django_settings.BASE_URL or "").rstrip("/")
    if not base:
        base = f"{request.scheme}://{request.get_host()}"
    return f"{base}/ics/{token}.ics"


def _serialize_membership(member) -> dict:
    return {
        "id": getattr(member, "id", ""),
        "calendar_id": getattr(member, "calendar_id", str(member.calendar.id)),
        "user_id": getattr(member, "user_id", str(member.user.id)),
        "email": member.user.email,
        "display_name": member.user.display_name,
        "role": member.role,
        "folder_id": getattr(member, "folder_id", None),
        "position": getattr(member, "position", 0),
    }


@router.get("/calendars", response=list[CalendarListOut], auth=django_auth)
def list_calendars(request):
    user = request.user
    direct = list(
        CalendarMember.objects.filter(user=user)
        .select_related("calendar")
        .order_by("position", "calendar__name")
    )
    seen = {str(m.calendar_id) for m in direct}
    results = []
    for membership in direct:
        results.append({
            "calendar": membership.calendar,
            "membership": _serialize_membership(membership),
        })

    # Group links
    my_group_ids = list(user.groups.values_list("id", flat=True))
    group_links = CalendarGroup.objects.filter(
        group_id__in=my_group_ids
    ).select_related("calendar")
    best = {}
    for gl in group_links:
        cid = str(gl.calendar_id)
        if cid in seen:
            continue
        if cid not in best or role_weight(gl.role) > role_weight(best[cid]["role"]):
            best[cid] = {"role": gl.role, "calendar": gl.calendar}
    for cid, info in best.items():
        seen.add(cid)
        calendar = info["calendar"]
        member = get_membership(calendar, user)
        results.append({
            "calendar": calendar,
            "membership": _serialize_membership(member),
        })

    # Public calendars
    for calendar in Calendar.objects.filter(is_public=True).exclude(id__in=seen):
        member = get_membership(calendar, user)
        results.append({
            "calendar": calendar,
            "membership": _serialize_membership(member),
        })

    return results


@router.post("/calendars", response=CalendarOut, auth=django_auth)
def create_calendar(request, payload: CalendarCreate):
    return create_calendar_for(
        request.user,
        name=payload.name,
        description=payload.description,
        force_all_day=payload.force_all_day,
        first_weekday=payload.first_weekday,
        show_weekends=payload.show_weekends,
        weekend_days=payload.weekend_days,
        show_week_numbers=payload.show_week_numbers,
        colors={field: getattr(payload, field) for field in COLOR_FIELDS},
    )


@router.get("/calendars/{calendar_id}", response=CalendarOut, auth=django_auth)
def get_calendar(request, calendar_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    out = CalendarOut.model_validate(calendar)
    out.my_membership = CalendarMemberOut.model_validate(_serialize_membership(membership))
    return out


@router.patch("/calendars/{calendar_id}", response=CalendarOut, auth=django_auth)
def update_calendar(request, calendar_id: str, payload: CalendarUpdate):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_owner(membership):
        raise HttpError(403, "Only the owner can update calendar details")

    data = payload.dict(exclude_unset=True)
    if "weekend_days" in data:
        data["weekend_days"] = sorted(set(data["weekend_days"]))
    if "url_path" in data and data["url_path"] is not None:
        url_path = data["url_path"]
        if url_path == "folder":
            raise HttpError(422, "This calendar URL is reserved")
        if Calendar.objects.exclude(id=calendar.id).filter(url_path=url_path).exists():
            raise HttpError(409, "This calendar URL is already in use")
        if Calendar.objects.exclude(id=calendar.id).filter(id=url_path).exists():
            raise HttpError(409, "This calendar URL is already in use")
    for attr, value in data.items():
        setattr(calendar, attr, value)
    try:
        with transaction.atomic():
            calendar.save()
    except IntegrityError as error:
        if "url_path" in data:
            raise HttpError(409, "This calendar URL is already in use") from error
        raise
    out = CalendarOut.model_validate(calendar)
    out.my_membership = CalendarMemberOut.model_validate(_serialize_membership(membership))
    return out


@router.delete("/calendars/{calendar_id}", auth=django_auth)
def delete_calendar(request, calendar_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_owner(membership):
        raise HttpError(403, "Only the owner can delete this calendar")
    calendar.delete()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get("/calendars/{calendar_id}/members", response=list[CalendarMemberOut], auth=django_auth)
def list_members(request, calendar_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    if get_membership(calendar, request.user) is None:
        raise HttpError(403, "Not a member of this calendar")
    members = CalendarMember.objects.filter(calendar=calendar).select_related("user")
    return [_serialize_membership(m) for m in members]


@router.post("/calendars/{calendar_id}/members", response=CalendarMemberOut, auth=django_auth)
def add_member(request, calendar_id: str, payload: CalendarMemberCreate):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_owner(membership):
        raise HttpError(403, "Only the owner can add members")
    if payload.role == Role.OWNER:
        raise HttpError(400, "Cannot add a second owner")
    if payload.role not in dict(Role.CHOICES):
        raise HttpError(422, "Invalid role")
    if get_direct_membership(calendar.id, payload.user_id):
        raise HttpError(400, "User is already a member")

    user = User.objects.get(id=payload.user_id)
    new_member = CalendarMember.objects.create(
        calendar=calendar,
        user=user,
        role=payload.role,
    )
    notify(
        [payload.user_id],
        "member_added",
        str(request.user.id),
        calendar.name,
        calendar_id=str(calendar.id),
        data={"role": payload.role},
    )
    return _serialize_membership(new_member)


@router.patch("/calendars/{calendar_id}/members/{user_id}", response=CalendarMemberOut, auth=django_auth)
def update_member(request, calendar_id: str, user_id: str, payload: CalendarMemberUpdate):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_owner(membership):
        raise HttpError(403, "Only the owner can change member roles")
    target = get_direct_membership(calendar.id, user_id)
    if target is None:
        raise HttpError(404, "Member not found")
    if target.role == Role.OWNER:
        raise HttpError(400, "Owner role cannot be changed")

    data = payload.dict(exclude_unset=True)
    if "role" in data:
        if data["role"] not in dict(Role.CHOICES):
            raise HttpError(422, "Invalid role")
        if target.role != data["role"]:
            target.role = data["role"]
            notify(
                [user_id],
                "member_role_changed",
                str(request.user.id),
                calendar.name,
                calendar_id=str(calendar.id),
                data={"role": data["role"]},
            )
    if "folder_id" in data:
        target.folder_id = data["folder_id"] or None
    if "position" in data:
        target.position = data["position"]
    target.save()
    return _serialize_membership(target)


@router.delete("/calendars/{calendar_id}/members/{user_id}", auth=django_auth)
def remove_member(request, calendar_id: str, user_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_owner(membership):
        raise HttpError(403, "Only the owner can remove members")
    target = get_direct_membership(calendar.id, user_id)
    if target is None:
        raise HttpError(404, "Member not found")
    if target.role == Role.OWNER:
        raise HttpError(400, "Cannot remove the owner")
    user = target.user
    target.delete()
    # Someone with no access left (not through a group or a public calendar either) can't decide on
    # bookings any more, so they stop being an approver, too.
    if get_membership(calendar, user) is None:
        CalendarApprover.objects.filter(calendar=calendar, user=user).delete()
        ResourceApprover.objects.filter(resource__calendar=calendar, user=user).delete()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------


@router.get("/calendars/{calendar_id}/feed-url", response=FeedUrlOut, auth=django_auth)
def get_feed_url(request, calendar_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    return {"feed_url": _make_feed_url(request, calendar.feed_token)}


@router.post("/calendars/{calendar_id}/feed-token/rotate", response=FeedTokenRotateOut, auth=django_auth)
def rotate_feed_token(request, calendar_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_owner(membership):
        raise HttpError(403, "Only the owner can rotate the feed token")
    calendar.feed_token = secrets.token_urlsafe(32)
    calendar.save()
    return {"feed_url": _make_feed_url(request, calendar.feed_token)}


# ---------------------------------------------------------------------------
# Default calendar approvers
# ---------------------------------------------------------------------------


def _require_owner_of_approvers(user, calendar: Calendar) -> None:
    membership = get_membership(calendar, user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_owner(membership):
        raise HttpError(403, "Only the owner can manage approvers")


@router.get("/calendars/{calendar_id}/approvers", response=list[ApproverOut], auth=django_auth)
def list_calendar_approvers(request, calendar_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    _require_owner_of_approvers(request.user, calendar)
    return approvers_of(CalendarApprover, calendar=calendar)


@router.put("/calendars/{calendar_id}/approvers", response=list[ApproverOut], auth=django_auth)
@transaction.atomic
def set_calendar_approvers(request, calendar_id: str, payload: ApproversIn):
    """Sets the default approvers, who decide on resources that have none of their own."""
    calendar = Calendar.objects.get(id=calendar_id)
    _require_owner_of_approvers(request.user, calendar)
    replace_approvers(CalendarApprover, "calendar", calendar, calendar.id, payload.user_ids)
    return approvers_of(CalendarApprover, calendar=calendar)


# ---------------------------------------------------------------------------
# Calendar group links
# ---------------------------------------------------------------------------


def _serialize_group_link(link: CalendarGroup) -> dict:
    return {
        "id": link.id,
        "group": {"id": link.group.id, "name": link.group.name},
        "role": link.role,
        "members": [
            {"id": user.id, "email": user.email, "display_name": user.display_name}
            for user in link.group.user_set.order_by("display_name")
        ],
    }


@router.get("/calendars/{calendar_id}/groups", response=list[CalendarGroupLinkOut], auth=django_auth)
def list_calendar_groups(request, calendar_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_owner(membership):
        raise HttpError(403, "Only the owner can manage group links")
    links = CalendarGroup.objects.filter(calendar=calendar).select_related("group")
    return [_serialize_group_link(link) for link in links]


@router.post("/calendars/{calendar_id}/groups", response=CalendarGroupLinkOut, auth=django_auth)
def add_calendar_group(request, calendar_id: str, payload: CalendarGroupLinkCreate):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_owner(membership):
        raise HttpError(403, "Only the owner can manage group links")
    group = UserGroup.objects.get(id=payload.group_id)
    if CalendarGroup.objects.filter(calendar=calendar, group=group).exists():
        raise HttpError(400, "Group is already linked to this calendar")
    link = CalendarGroup.objects.create(calendar=calendar, group=group, role=payload.role)
    return _serialize_group_link(link)


@router.patch("/calendars/{calendar_id}/groups/{link_id}", response=CalendarGroupLinkOut, auth=django_auth)
def update_calendar_group(request, calendar_id: str, link_id: str, payload: CalendarGroupLinkUpdate):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_owner(membership):
        raise HttpError(403, "Only the owner can manage group links")
    link = CalendarGroup.objects.select_related("group").get(id=link_id, calendar=calendar)
    if payload.role is not None:
        link.role = payload.role
    link.save()
    return _serialize_group_link(link)


@router.delete("/calendars/{calendar_id}/groups/{link_id}", auth=django_auth)
def delete_calendar_group(request, calendar_id: str, link_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_owner(membership):
        raise HttpError(403, "Only the owner can manage group links")
    CalendarGroup.objects.filter(id=link_id, calendar=calendar).delete()
    return {"ok": True}
