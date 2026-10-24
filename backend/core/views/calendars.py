"""
Calendar, membership, feed and group-link endpoints.
"""

import secrets

from django.conf import settings
from django.db import IntegrityError, transaction
from ninja import Router
from ninja.errors import HttpError

from core.models import (
    Calendar,
    CalendarApprover,
    CalendarGroup,
    CalendarMember,
    FeedToken,
    ResourceApprover,
    User,
    UserGroup,
)
from core.models.base import MembershipSource, Role
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
    PublicCalendarOut,
)
from core.services.calendars import create_calendar as create_calendar_for
from core.services.memberships import next_sidebar_position, sync_membership
from core.services.notifications import notify
from core.services.permissions import (
    MembershipInfo,
    get_direct_membership,
    get_member_calendar,
    get_membership,
    memberships_of,
)
from core.views.common import approvers_of, replace_approvers

router = Router()


def _make_feed_url(request, token: str) -> str:
    base = (settings.BASE_URL or "").rstrip("/")
    if not base:
        base = f"{request.scheme}://{request.get_host()}"
    return f"{base}/ics/{token}.ics"


def _serialize_membership(member: CalendarMember | MembershipInfo) -> dict:
    return {
        "id": member.id,
        "calendar_id": member.calendar_id,
        "user_id": member.user_id,
        "email": member.user.email,
        "display_name": member.user.display_name,
        "role": member.role,
        "folder_id": member.folder_id,
        "position": member.position,
    }


ACCESS_OF_SOURCE = {
    MembershipSource.DIRECT: "member",
    MembershipSource.GROUP: "group",
    MembershipSource.PUBLIC: "public",
}


def sidebar_calendars_of(user) -> list[dict]:
    """The calendars of the user's sidebar: one membership each, granted directly, from a group, or added."""
    memberships = list(
        CalendarMember.objects.filter(user=user).select_related("calendar").order_by("position", "calendar__name")
    )
    # The role of a membership from a group or a public calendar is worked out afresh (see memberships_of).
    accesses = memberships_of(user, [m.calendar for m in memberships])
    results = []
    for membership in memberships:
        access = accesses.get(membership.calendar_id)
        if access is None:
            continue
        results.append({
            "calendar": membership.calendar,
            "membership": _serialize_membership(access),
            "access": ACCESS_OF_SOURCE[membership.source],
        })
    return results


@router.get("/calendars", response=list[CalendarListOut])
def list_calendars(request):
    return sidebar_calendars_of(request.user)


# ---------------------------------------------------------------------------
# Public calendars: added to one's sidebar by choice
# ---------------------------------------------------------------------------


@router.get("/calendars/public", response=list[PublicCalendarOut])
def public_calendars(request):
    """Public calendars the user doesn't have through a direct membership or a group anyway."""
    user = request.user
    sources = dict(CalendarMember.objects.filter(user=user).values_list("calendar_id", "source"))
    calendars = Calendar.objects.filter(is_public=True).select_related("owner").order_by("name")
    return [
        {
            "id": calendar.id,
            "name": calendar.name,
            "description": calendar.description,
            "owner_name": calendar.owner.display_name or calendar.owner.email,
            "added": sources.get(calendar.id) == MembershipSource.PUBLIC,
        }
        for calendar in calendars
        if sources.get(calendar.id) in (None, MembershipSource.PUBLIC)
    ]


def _public_calendar(calendar_id: str) -> Calendar:
    calendar = Calendar.objects.filter(id=calendar_id, is_public=True).first()
    if calendar is None:
        raise HttpError(404, "Calendar not found")
    return calendar


@router.put("/calendars/{calendar_id}/subscription")
def add_public_calendar(request, calendar_id: str):
    """Adds a public calendar to the sidebar, at its end; its public role applies (see get_membership)."""
    calendar = _public_calendar(calendar_id)
    if not CalendarMember.objects.filter(calendar=calendar, user=request.user).exists():
        CalendarMember.objects.create(
            calendar=calendar,
            user=request.user,
            source=MembershipSource.PUBLIC,
            role=None,
            position=next_sidebar_position(request.user.id),
        )
    return {"ok": True}


@router.delete("/calendars/{calendar_id}/subscription")
def remove_public_calendar(request, calendar_id: str):
    """Takes a public calendar the user added out of the sidebar again."""
    # Deleting a queryset still sends post_delete, which updates the user's other tabs.
    CalendarMember.objects.filter(calendar_id=calendar_id, user=request.user, source=MembershipSource.PUBLIC).delete()
    return {"ok": True}


@router.post("/calendars", response=CalendarOut)
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


@router.get("/calendars/{calendar_id}", response=CalendarOut)
def get_calendar(request, calendar_id: str):
    calendar, membership = get_member_calendar(calendar_id, request.user)
    out = CalendarOut.model_validate(calendar)
    out.my_membership = CalendarMemberOut.model_validate(_serialize_membership(membership))
    return out


@router.patch("/calendars/{calendar_id}", response=CalendarOut)
def update_calendar(request, calendar_id: str, payload: CalendarUpdate):
    calendar, membership = get_member_calendar(
        calendar_id, request.user, Role.MANAGE, "Only who manages the calendar can update its details"
    )

    data = payload.dict(exclude_unset=True)
    if data.get("weekend_days") is not None:
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


@router.delete("/calendars/{calendar_id}")
def delete_calendar(request, calendar_id: str):
    calendar, _ = get_member_calendar(
        calendar_id, request.user, Role.OWNER, "Only the owner can delete this calendar"
    )
    calendar.delete()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get("/calendars/{calendar_id}/members", response=list[CalendarMemberOut])
def list_members(request, calendar_id: str):
    calendar, _ = get_member_calendar(calendar_id, request.user)
    # Granted ones: memberships from a group show under the group, added public calendars nowhere.
    members = CalendarMember.objects.filter(calendar=calendar, source=MembershipSource.DIRECT).select_related("user")
    return [_serialize_membership(m) for m in members]


@router.post("/calendars/{calendar_id}/members", response=CalendarMemberOut)
def add_member(request, calendar_id: str, payload: CalendarMemberCreate):
    calendar, _ = get_member_calendar(
        calendar_id, request.user, Role.MANAGE, "Only who manages the calendar can add members"
    )
    if payload.role == Role.OWNER:
        raise HttpError(400, "Cannot add a second owner")
    if get_direct_membership(calendar.id, payload.user_id):
        raise HttpError(400, "User is already a member")

    user = User.objects.get(id=payload.user_id)
    # Who has the calendar through a group or added it keeps its place in their sidebar.
    new_member = CalendarMember.objects.filter(calendar=calendar, user=user).first()
    if new_member is None:
        new_member = CalendarMember.objects.create(
            calendar=calendar,
            user=user,
            role=payload.role,
            position=next_sidebar_position(user.id),
        )
    else:
        new_member.source, new_member.role = MembershipSource.DIRECT, payload.role
        new_member.save(update_fields=["source", "role"])
    notify(
        [payload.user_id],
        "member_added",
        str(request.user.id),
        calendar.name,
        calendar_id=str(calendar.id),
        data={"role": payload.role},
    )
    return _serialize_membership(new_member)


@router.patch("/calendars/{calendar_id}/members/{user_id}", response=CalendarMemberOut)
def update_member(request, calendar_id: str, user_id: str, payload: CalendarMemberUpdate):
    calendar, _ = get_member_calendar(
        calendar_id, request.user, Role.MANAGE, "Only who manages the calendar can change member roles"
    )
    target = get_direct_membership(calendar.id, user_id)
    if target is None:
        raise HttpError(404, "Member not found")
    if target.role == Role.OWNER:
        raise HttpError(400, "Owner role cannot be changed")

    data = payload.dict(exclude_unset=True)
    if "role" in data:
        if data["role"] == Role.OWNER:
            raise HttpError(400, "Cannot make a second owner")
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


@router.delete("/calendars/{calendar_id}/members/{user_id}")
def remove_member(request, calendar_id: str, user_id: str):
    calendar, _ = get_member_calendar(
        calendar_id, request.user, Role.MANAGE, "Only who manages the calendar can remove members"
    )
    target = get_direct_membership(calendar.id, user_id)
    if target is None:
        raise HttpError(404, "Member not found")
    if target.role == Role.OWNER:
        raise HttpError(400, "Cannot remove the owner")
    user = target.user
    # What the user still has through a group (or, a public calendar in their sidebar, its public role)
    # takes the membership's place; with nothing left it goes.
    sync_membership(user.id, calendar, release_direct=True)
    # Someone with no access left (not through a group or a public calendar either) can't decide on
    # bookings any more, so they stop being an approver, too.
    if get_membership(calendar, user) is None:
        CalendarApprover.objects.filter(calendar=calendar, user=user).delete()
        ResourceApprover.objects.filter(resource__calendar=calendar, user=user).delete()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------


# Each member has a feed URL of their own, which stops working when they lose access to the calendar
# (views.feed); a shared one would keep working for whoever once had it.


@router.get("/calendars/{calendar_id}/feed-url", response=FeedUrlOut)
def get_feed_url(request, calendar_id: str):
    calendar, _ = get_member_calendar(calendar_id, request.user)
    feed, _ = FeedToken.objects.get_or_create(
        calendar=calendar, user=request.user, defaults={"token": secrets.token_urlsafe(32)}
    )
    return {"feed_url": _make_feed_url(request, feed.token)}


@router.post("/calendars/{calendar_id}/feed-token/rotate", response=FeedTokenRotateOut)
def rotate_feed_token(request, calendar_id: str):
    """A new feed URL for the user, e.g. after they shared theirs by mistake."""
    calendar, _ = get_member_calendar(calendar_id, request.user)
    feed, _ = FeedToken.objects.update_or_create(
        calendar=calendar, user=request.user, defaults={"token": secrets.token_urlsafe(32)}
    )
    return {"feed_url": _make_feed_url(request, feed.token)}


# ---------------------------------------------------------------------------
# Default calendar approvers
# ---------------------------------------------------------------------------


def _calendar_to_manage_approvers(user, calendar_id: str) -> Calendar:
    calendar, _ = get_member_calendar(
        calendar_id, user, Role.MANAGE, "Only who manages the calendar can manage approvers"
    )
    return calendar


@router.get("/calendars/{calendar_id}/approvers", response=list[ApproverOut])
def list_calendar_approvers(request, calendar_id: str):
    calendar = _calendar_to_manage_approvers(request.user, calendar_id)
    return approvers_of(CalendarApprover, calendar=calendar)


@router.put("/calendars/{calendar_id}/approvers", response=list[ApproverOut])
@transaction.atomic
def set_calendar_approvers(request, calendar_id: str, payload: ApproversIn):
    """Sets the default approvers, who decide on resources that have none of their own."""
    calendar = _calendar_to_manage_approvers(request.user, calendar_id)
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
            # Sorted here, so that the members prefetched for a list of links serve (list_calendar_groups).
            for user in sorted(link.group.user_set.all(), key=lambda user: user.display_name)
        ],
    }


@router.get("/calendars/{calendar_id}/groups", response=list[CalendarGroupLinkOut])
def list_calendar_groups(request, calendar_id: str):
    calendar, _ = get_member_calendar(
        calendar_id, request.user, Role.MANAGE, "Only who manages the calendar can manage group links"
    )
    links = CalendarGroup.objects.filter(calendar=calendar).select_related("group").prefetch_related("group__user_set")
    return [_serialize_group_link(link) for link in links]


@router.post("/calendars/{calendar_id}/groups", response=CalendarGroupLinkOut)
def add_calendar_group(request, calendar_id: str, payload: CalendarGroupLinkCreate):
    calendar, _ = get_member_calendar(
        calendar_id, request.user, Role.MANAGE, "Only who manages the calendar can manage group links"
    )
    group = UserGroup.objects.get(id=payload.group_id)
    if CalendarGroup.objects.filter(calendar=calendar, group=group).exists():
        raise HttpError(400, "Group is already linked to this calendar")
    link = CalendarGroup.objects.create(calendar=calendar, group=group, role=payload.role)
    return _serialize_group_link(link)


@router.patch("/calendars/{calendar_id}/groups/{link_id}", response=CalendarGroupLinkOut)
def update_calendar_group(request, calendar_id: str, link_id: str, payload: CalendarGroupLinkUpdate):
    calendar, _ = get_member_calendar(
        calendar_id, request.user, Role.MANAGE, "Only who manages the calendar can manage group links"
    )
    link = CalendarGroup.objects.select_related("group").get(id=link_id, calendar=calendar)
    if payload.role is not None:
        link.role = payload.role
    link.save()
    return _serialize_group_link(link)


@router.delete("/calendars/{calendar_id}/groups/{link_id}")
def delete_calendar_group(request, calendar_id: str, link_id: str):
    calendar, _ = get_member_calendar(
        calendar_id, request.user, Role.MANAGE, "Only who manages the calendar can manage group links"
    )
    CalendarGroup.objects.filter(id=link_id, calendar=calendar).delete()
    return {"ok": True}
