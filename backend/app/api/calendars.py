import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Calendar, CalendarApprover, CalendarMember, Folder, Role, User, get_or_create_app_settings
from app.schemas import (
    ApproverCreate,
    CalendarCreate,
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
from app.services.permissions import (
    get_membership,
    has_at_least_role,
    is_owner,
    require_membership,
)

router = APIRouter(prefix="/calendars", tags=["calendars"])


def _make_feed_url(request: Request, token: str) -> str:
    return f"{request.url.scheme}://{request.url.netloc}/ics/{token}.ics"


@router.get("", response_model=List[CalendarListOut])
def list_calendars(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[dict]:
    memberships = (
        db.query(CalendarMember)
        .filter(CalendarMember.user_id == current_user.id)
        .join(Calendar)
        .order_by(CalendarMember.position.asc(), Calendar.name.asc())
        .all()
    )
    return [
        {
            "calendar": CalendarOut.model_validate(membership.calendar),
            "membership": _serialize_membership(membership),
        }
        for membership in memberships
    ]


@router.post("", response_model=CalendarOut, status_code=status.HTTP_201_CREATED)
def create_calendar(
    data: CalendarCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Calendar:
    app_settings = get_or_create_app_settings(db)
    first_weekday = data.first_weekday if data.first_weekday is not None else app_settings.default_first_weekday
    show_weekends = data.show_weekends if data.show_weekends is not None else app_settings.default_show_weekends
    weekend_days = data.weekend_days if data.weekend_days is not None else app_settings.default_weekend_days
    calendar = Calendar(
        name=data.name,
        description=data.description,
        color=data.color,
        dark_color=data.dark_color,
        force_all_day=data.force_all_day,
        first_weekday=first_weekday,
        show_weekends=show_weekends,
        weekend_days=sorted(set(weekend_days)),
        today_color=data.today_color,
        weekend_color=data.weekend_color,
        owner_id=current_user.id,
        feed_token=secrets.token_urlsafe(32),
    )
    db.add(calendar)
    db.flush()
    owner_membership = CalendarMember(
        calendar_id=calendar.id,
        user_id=current_user.id,
        role=Role.OWNER.value,
        folder_id=None,
        position=0,
    )
    db.add(owner_membership)
    db.commit()
    db.refresh(calendar)
    return calendar


def _serialize_membership(member: CalendarMember) -> CalendarMemberOut:
    return CalendarMemberOut(
        id=member.id,
        calendar_id=member.calendar_id,
        user_id=member.user_id,
        email=member.user.email,
        display_name=member.user.display_name,
        role=member.role,
        folder_id=member.folder_id,
        position=member.position,
    )


@router.get("/{calendar_id}", response_model=CalendarOut)
def get_calendar(
    calendar_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Calendar:
    membership = require_membership(db, calendar_id, current_user.id)
    membership_out = _serialize_membership(membership)
    out = CalendarOut.model_validate(membership.calendar)
    out.my_membership = membership_out
    return out


@router.patch("/{calendar_id}", response_model=CalendarOut)
def update_calendar(
    calendar_id: str,
    data: CalendarUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Calendar:
    membership = require_membership(db, calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can update calendar details",
        )
    calendar = membership.calendar
    if data.name is not None:
        calendar.name = data.name
    if data.description is not None:
        calendar.description = data.description
    if data.color is not None:
        calendar.color = data.color
    if data.dark_color is not None:
        calendar.dark_color = data.dark_color
    if data.force_all_day is not None:
        calendar.force_all_day = data.force_all_day
    if data.first_weekday is not None:
        calendar.first_weekday = data.first_weekday
    if data.show_weekends is not None:
        calendar.show_weekends = data.show_weekends
    if data.weekend_days is not None:
        calendar.weekend_days = sorted(set(data.weekend_days))
    if data.today_color is not None:
        calendar.today_color = data.today_color
    if data.dark_today_color is not None:
        calendar.dark_today_color = data.dark_today_color
    if data.weekend_color is not None:
        calendar.weekend_color = data.weekend_color
    if data.dark_weekend_color is not None:
        calendar.dark_weekend_color = data.dark_weekend_color
    db.commit()
    db.refresh(calendar)
    out = CalendarOut.model_validate(calendar)
    out.my_membership = _serialize_membership(membership)
    return out


@router.delete("/{calendar_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_calendar(
    calendar_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    membership = require_membership(db, calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can delete this calendar",
        )
    db.delete(membership.calendar)
    db.commit()


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get("/{calendar_id}/members", response_model=List[CalendarMemberOut])
def list_members(
    calendar_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[CalendarMemberOut]:
    require_membership(db, calendar_id, current_user.id)
    members = (
        db.query(CalendarMember)
        .filter(CalendarMember.calendar_id == calendar_id)
        .join(User)
        .all()
    )
    return [_serialize_membership(member) for member in members]


@router.post("/{calendar_id}/members", response_model=CalendarMemberOut, status_code=201)
def add_member(
    calendar_id: str,
    data: CalendarMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CalendarMember:
    membership = require_membership(db, calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can add members",
        )
    if data.role == Role.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add a second owner",
        )
    user = db.query(User).filter(User.id == data.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    existing = get_membership(db, calendar_id, data.user_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member",
        )
    if data.role not in {r.value for r in Role}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid role",
        )
    new_member = CalendarMember(
        calendar_id=calendar_id,
        user_id=data.user_id,
        role=data.role,
    )
    db.add(new_member)
    db.commit()
    db.refresh(new_member)
    return _serialize_membership(new_member)


@router.patch("/{calendar_id}/members/me", response_model=MyMembershipOut)
def update_my_membership(
    calendar_id: str,
    data: CalendarMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CalendarMember:
    membership = require_membership(db, calendar_id, current_user.id)
    if data.role is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role",
        )
    update_data = data.model_dump(exclude_unset=True)
    if "folder_id" in update_data:
        if update_data["folder_id"]:
            folder = db.query(Folder).filter(
                Folder.id == update_data["folder_id"],
                Folder.user_id == current_user.id,
            ).first()
            if folder is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Folder not found",
                )
            membership.folder_id = folder.id
        else:
            membership.folder_id = None
    if "position" in update_data:
        membership.position = update_data["position"]
    db.commit()
    db.refresh(membership)
    return MyMembershipOut.model_validate(membership)


@router.patch("/{calendar_id}/members/{user_id}", response_model=CalendarMemberOut)
def update_member(
    calendar_id: str,
    user_id: str,
    data: CalendarMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CalendarMember:
    membership = require_membership(db, calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can change member roles",
        )
    target = get_membership(db, calendar_id, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    if target.role == Role.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owner role cannot be changed",
        )
    if data.role is not None:
        if data.role not in {r.value for r in Role}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid role",
            )
        target.role = data.role
    db.commit()
    db.refresh(target)
    return _serialize_membership(target)


@router.delete("/{calendar_id}/members/{user_id}", status_code=204)
def remove_member(
    calendar_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    membership = require_membership(db, calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can remove members",
        )
    target = get_membership(db, calendar_id, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    if target.role == Role.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the owner",
        )
    db.delete(target)
    db.commit()


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------


@router.get("/{calendar_id}/feed-url", response_model=FeedUrlOut)
def get_feed_url(
    calendar_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    membership = require_membership(db, calendar_id, current_user.id)
    return {"feed_url": _make_feed_url(request, membership.calendar.feed_token)}


@router.post("/{calendar_id}/feed-token/rotate", response_model=FeedTokenRotateOut)
def rotate_feed_token(
    calendar_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    membership = require_membership(db, calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can rotate the feed token",
        )
    membership.calendar.feed_token = secrets.token_urlsafe(32)
    db.commit()
    db.refresh(membership.calendar)
    return {"feed_url": _make_feed_url(request, membership.calendar.feed_token)}


# ---------------------------------------------------------------------------
# Default calendar approvers
# ---------------------------------------------------------------------------


@router.get("/{calendar_id}/approvers", response_model=List[CalendarMemberOut])
def list_calendar_approvers(
    calendar_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[CalendarApprover]:
    membership = require_membership(db, calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can manage approvers",
        )
    approvers = (
        db.query(CalendarApprover)
        .filter(CalendarApprover.calendar_id == calendar_id)
        .join(User)
        .all()
    )
    return [
        CalendarMemberOut(
            id=approver.id,
            calendar_id=calendar_id,
            user_id=approver.user_id,
            email=approver.user.email,
            display_name=approver.user.display_name,
            role="",
            folder_id=None,
            position=0,
        )
        for approver in approvers
    ]


@router.post("/{calendar_id}/approvers", response_model=CalendarMemberOut, status_code=201)
def add_calendar_approver(
    calendar_id: str,
    data: ApproverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CalendarMemberOut:
    membership = require_membership(db, calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can add approvers",
        )
    target_membership = get_membership(db, calendar_id, data.user_id)
    if target_membership is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approver must be a calendar member",
        )
    existing = (
        db.query(CalendarApprover)
        .filter_by(calendar_id=calendar_id, user_id=data.user_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a default approver",
        )
    approver = CalendarApprover(
        calendar_id=calendar_id,
        user_id=data.user_id,
    )
    db.add(approver)
    db.commit()
    db.refresh(approver)
    return CalendarMemberOut(
        id=approver.id,
        calendar_id=calendar_id,
        user_id=approver.user_id,
        email=approver.user.email,
        display_name=approver.user.display_name,
        role="",
        folder_id=None,
        position=0,
    )


@router.delete("/{calendar_id}/approvers/{user_id}", status_code=204)
def remove_calendar_approver(
    calendar_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    membership = require_membership(db, calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can remove approvers",
        )
    approver = (
        db.query(CalendarApprover)
        .filter_by(calendar_id=calendar_id, user_id=user_id)
        .first()
    )
    if approver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approver not found",
        )
    db.delete(approver)
    db.commit()
