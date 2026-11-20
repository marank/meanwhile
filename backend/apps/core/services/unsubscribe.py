"""
Unsubscribing by the links in an email's footer, without signing in: from a kind of email, or from
all emails about one event (a series as a whole).

A link carries a signed token (SECRET_KEY) naming the user and the kind or the event; it doesn't
expire, so an old email still unsubscribes. The app's page asks before it does (mail scanners open
links), and can undo it: there is no switch for an event in the app.
"""

from dataclasses import dataclass
from uuid import UUID

from django.core import signing

from apps.core.models import Event, EventEmailMute, User

_SALT = "core.email-unsubscribe"


@dataclass
class Subscription:
    """What a link stops: a kind of email, or the emails about an event."""

    user: User
    kind: str | None = None
    event: Event | None = None


def make_token(user: User, kind: str | None = None, event: Event | None = None) -> str:
    data = {"user": str(user.id), "kind": kind} if event is None else {"user": str(user.id), "event": str(event.id)}
    return signing.dumps(data, salt=_SALT, compress=True)


def read_token(token: str, kinds: set[str]) -> Subscription | None:
    """What a token stands for, if it is genuine and its user (and event) still exist."""
    try:
        data = signing.loads(token, salt=_SALT)
    except signing.BadSignature:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("user"), str):
        return None
    user = User.objects.filter(id=data["user"], is_active=True).first()
    if user is None:
        return None
    if isinstance(data.get("event"), str):
        event = Event.objects.filter(id=data["event"]).first()
        return Subscription(user, event=event) if event else None
    return Subscription(user, kind=data["kind"]) if data.get("kind") in kinds else None


def series_id(event: Event) -> UUID:
    """Mutes are for a series as a whole: the event they are stored for."""
    return event.parent_id or event.id


def muted_user_ids(event: Event) -> set[str]:
    """Who wants no more emails about the event (its series)."""
    return {
        str(user_id)
        for user_id in EventEmailMute.objects.filter(event_id=series_id(event)).values_list("user_id", flat=True)
    }


def set_subscribed(subscription: Subscription, subscribed: bool) -> None:
    user = subscription.user
    if subscription.event is not None:
        if subscribed:
            EventEmailMute.objects.filter(user=user, event=subscription.event).delete()
        else:
            EventEmailMute.objects.get_or_create(user=user, event=subscription.event)
        return
    assert subscription.kind is not None
    user.email_notifications = {**(user.email_notifications or {}), subscription.kind: subscribed}
    user.save(update_fields=["email_notifications"])


def is_muted(user: User, event: Event) -> bool:
    return EventEmailMute.objects.filter(user=user, event_id=series_id(event)).exists()
