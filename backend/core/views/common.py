"""
Common view helpers.
"""

from ninja.errors import HttpError


def require_admin(request):
    if not request.user.is_authenticated or not getattr(request.user, "is_admin", False):
        raise HttpError(403, "Admin access required")


def get_detail(message: str, status: int = 400):
    raise HttpError(status, {"detail": message})
