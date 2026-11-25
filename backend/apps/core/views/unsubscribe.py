"""
Unsubscribing by the links in an email's footer, from a kind of email or from the emails about one
event: the token in the link names the user and what to stop (apps.core.services.unsubscribe), so no
session is needed. Mail programs that offer to unsubscribe (the List-Unsubscribe header) post to the
same address; the page undoes it with DELETE.
"""

from django.http import HttpRequest
from django.utils.translation import gettext
from ninja import Router
from ninja.errors import HttpError

from apps.core.schemas import UnsubscribeOut
from apps.core.services.notifications import EMAIL_KINDS, email_preferences
from apps.core.services.unsubscribe import Subscription, is_muted, read_token, set_subscribed

router = Router()


def _subscription(token: str) -> Subscription:
    found = read_token(token, set(EMAIL_KINDS))
    if found is None:
        raise HttpError(404, gettext("This link is not valid"))
    return found


def _serialize(subscription: Subscription) -> dict[str, object]:
    user, event = subscription.user, subscription.event
    if event is not None:
        return {"email": user.email, "kind": None, "event_title": event.title, "subscribed": not is_muted(user, event)}
    assert subscription.kind is not None
    subscribed = email_preferences(user)[subscription.kind]
    return {"email": user.email, "kind": subscription.kind, "event_title": None, "subscribed": subscribed}


@router.get("/unsubscribe/{token}", response=UnsubscribeOut, auth=None)
def get_subscription(request: HttpRequest, token: str) -> dict[str, object]:
    return _serialize(_subscription(token))


@router.post("/unsubscribe/{token}", response=UnsubscribeOut, auth=None)
def unsubscribe_by_link(request: HttpRequest, token: str) -> dict[str, object]:
    subscription = _subscription(token)
    set_subscribed(subscription, False)
    return _serialize(subscription)


@router.delete("/unsubscribe/{token}", response=UnsubscribeOut, auth=None)
def resubscribe_by_link(request: HttpRequest, token: str) -> dict[str, object]:
    subscription = _subscription(token)
    set_subscribed(subscription, True)
    return _serialize(subscription)
