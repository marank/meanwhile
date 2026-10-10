"""
Calendar, membership, feed and group-link endpoints.
"""

import secrets

from django.db import transaction
from ninja import Router
from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import (
    Calendar,
    CalendarApprover,
    CalendarGroup,
    CalendarMember,
    Folder,
    User,
    UserGroup,
    get_or_create_app_settings,
)
from core.models.base import Role
from core.models.calendar_colors import COLOR_FIELDS, DEFAULT_COLORS
from core.schemas import (
    ApproverCreate,
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
    MyMembershipOut,
)
from core.services.notifications import notify
from core.services.permissions import (
    get_direct_membership,
    get_membership,
    has_at_least_role,
    is_owner,
    role_weight,
)

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
    user = request.user
    app_settings = get_or_create_app_settings()
    defaults = {
        "first_weekday": payload.first_weekday if payload.first_weekday is not None else app_settings.default_first_weekday,
        "show_weekends": payload.show_weekends if payload.show_weekends is not None else app_settings.default_show_weekends,
        "weekend_days": sorted(set(payload.weekend_days)) if payload.weekend_days is not None else app_settings.default_weekend_days,
        "show_week_numbers": payload.show_week_numbers if payload.show_week_numbers is not None else app_settings.default_show_week_numbers,
    }
    calendar = Calendar.objects.create(
        name=payload.name,
        description=payload.description,
        force_all_day=payload.force_all_day,
        first_weekday=defaults["first_weekday"],
        show_weekends=defaults["show_weekends"],
        weekend_days=defaults["weekend_days"],
        show_week_numbers=defaults["show_week_numbers"],
        **{field: getattr(payload, field) or DEFAULT_COLORS[field] for field in COLOR_FIELDS},
        owner=user,
        feed_token=secrets.token_urlsafe(32),
    )
    CalendarMember.objects.create(
        calendar=calendar,
        user=user,
        role=Role.OWNER,
        folder_id=None,
        position=0,
    )
    return calendar


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
    for attr, value in data.items():
        setattr(calendar, attr, value)
    calendar.save()
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


@router.patch("/calendars/{calendar_id}/members/me", response=MyMembershipOut, auth=django_auth)
def update_my_membership(request, calendar_id: str, payload: CalendarMemberUpdate):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    data = payload.dict(exclude_unset=True)
    if "role" in data:
        raise HttpError(400, "You cannot change your own role")
    if "folder_id" in data:
        folder_id = data["folder_id"]
        if folder_id:
            folder = Folder.objects.filter(id=folder_id, user=request.user).first()
            if folder is None:
                raise HttpError(404, "Folder not found")
            membership.folder_id = folder.id
        else:
            membership.folder_id = None
    if "position" in data:
        membership.position = data["position"]
    membership.save()
    return membership


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
    target.delete()
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


@router.get("/calendars/{calendar_id}/approvers", response=list[CalendarMemberOut], auth=django_auth)
def list_calendar_approvers(request, calendar_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_owner(membership):
        raise HttpError(403, "Only the owner can manage approvers")
    approvers = CalendarApprover.objects.filter(calendar=calendar).select_related("user")
    return [
        {
            "id": a.id,
            "calendar_id": str(calendar.id),
            "user_id": a.user_id,
            "email": a.user.email,
            "display_name": a.user.display_name,
            "role": "",
            "folder_id": None,
            "position": 0,
        }
        for a in approvers
    ]


@router.post("/calendars/{calendar_id}/approvers", response=CalendarMemberOut, auth=django_auth)
def add_calendar_approver(request, calendar_id: str, payload: ApproverCreate):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_owner(membership):
        raise HttpError(403, "Only the owner can add approvers")
    if get_direct_membership(calendar.id, payload.user_id) is None:
        raise HttpError(400, "Approver must be a calendar member")
    if CalendarApprover.objects.filter(calendar=calendar, user_id=payload.user_id).exists():
        raise HttpError(400, "User is already a default approver")

    user = User.objects.get(id=payload.user_id)
    approver = CalendarApprover.objects.create(calendar=calendar, user=user)
    return {
        "id": approver.id,
        "calendar_id": str(calendar.id),
        "user_id": approver.user_id,
        "email": user.email,
        "display_name": user.display_name,
        "role": "",
        "folder_id": None,
        "position": 0,
    }


@router.delete("/calendars/{calendar_id}/approvers/{user_id}", auth=django_auth)
def remove_calendar_approver(request, calendar_id: str, user_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_owner(membership):
        raise HttpError(403, "Only the owner can remove approvers")
    CalendarApprover.objects.filter(calendar=calendar, user_id=user_id).delete()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Calendar group links
# ---------------------------------------------------------------------------


def _serialize_group_link(link: CalendarGroup) -> dict:
    return {
        "id": link.id,
        "group": {"id": link.group.id, "name": link.group.name},
        "role": link.role,
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
