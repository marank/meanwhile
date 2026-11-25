"""
Comments on events, and who hears of a new one.
"""

from django.utils.translation import gettext
from ninja.errors import HttpError

from apps.core.models import Event, EventComment, User
from apps.core.services.notifications import notify
from apps.core.services.permissions import can_see_event, get_membership


def add_comment(event: Event, author: User, body: str) -> EventComment:
    """Adds the comment and tells the event's creator and who commented before."""
    body = body.strip()
    if not body:
        raise HttpError(422, gettext("Comment must not be empty"))
    comment = EventComment.objects.create(event=event, author=author, body=body)
    previous_commenters = EventComment.objects.filter(event=event).values_list("author_id", flat=True).distinct()
    # Only who may still see the event: the notification carries the comment.
    recipients = [
        user
        for user in User.objects.filter(id__in={event.creator_id, *previous_commenters}, is_active=True)
        if (access := get_membership(event.calendar, user)) is not None and can_see_event(event, user, access)
    ]
    notify(
        [str(user.id) for user in recipients],
        "comment_added",
        str(author.id),
        event.title,
        calendar_id=str(event.calendar_id),
        event_id=str(event.id),
        data={"comment": body[:1000]},
    )
    return comment
