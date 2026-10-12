"""
Common view helpers.
"""

from ninja.errors import HttpError

from core.models import User
from core.schemas import ApproverOut
from core.services.permissions import get_direct_membership


def require_admin(request):
    if not request.user.is_authenticated or not getattr(request.user, "is_admin", False):
        raise HttpError(403, "Admin access required")


def get_detail(message: str, status: int = 400):
    raise HttpError(status, {"detail": message})


def approvers_of(approver_model, **owner) -> list[ApproverOut]:
    """The approvers of a calendar or resource (`approver_model` filtered by `owner`), by name."""
    rows = approver_model.objects.filter(**owner).select_related("user").order_by("user__display_name", "user__email")
    return [ApproverOut(user_id=a.user_id, email=a.user.email, display_name=a.user.display_name) for a in rows]


def replace_approvers(approver_model, owner_field: str, owner, calendar_id, user_ids: list[str]) -> None:
    """Makes `user_ids` the approvers of the owner (a calendar or resource); each must be a direct member."""
    wanted = list(dict.fromkeys(user_ids))
    for user_id in wanted:
        if get_direct_membership(calendar_id, user_id) is None:
            raise HttpError(400, "Approver must be a calendar member")
    current = approver_model.objects.filter(**{owner_field: owner})
    current.exclude(user_id__in=wanted).delete()
    missing = set(wanted) - set(current.values_list("user_id", flat=True))
    approver_model.objects.bulk_create(
        [approver_model(**{owner_field: owner, "user": user}) for user in User.objects.filter(id__in=missing)]
    )
