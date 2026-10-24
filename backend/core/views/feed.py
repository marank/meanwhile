"""
Public iCal feed view.
"""

import hashlib

from django.db.models import Count, Max, Prefetch
from django.http import HttpResponse
from django.utils.cache import get_conditional_response
from django.utils.http import http_date

from core.models import Calendar, Category, DeletedEvent, Event, FeedToken, Resource
from core.models.base import EventStatus
from core.services.ical import build_calendar_feed
from core.services.permissions import get_membership


def _feed_version(calendar: Calendar) -> tuple[str, int]:
    """ETag and last change (whole seconds) of the feed, without building it.

    The feed changes only along with these: the calendar, its events (hidden ones too: one that turns
    hidden leaves the feed), the deleted ones, and the categories and resources whose names it shows.
    """
    events = Event.objects.filter(calendar=calendar).aggregate(changed=Max("updated_at"), count=Count("id"))
    changes = [
        calendar.updated_at,
        events["changed"],
        DeletedEvent.objects.filter(calendar_id=calendar.id).aggregate(m=Max("deleted_at"))["m"],
        Category.objects.filter(calendar=calendar).aggregate(m=Max("updated_at"))["m"],
        Resource.objects.filter(calendar=calendar).aggregate(m=Max("updated_at"))["m"],
    ]
    version = f"{calendar.id}/{events['count']}/" + "/".join(t.isoformat() if t else "-" for t in changes)
    etag = f'"{hashlib.sha256(version.encode()).hexdigest()[:32]}"'
    return etag, int(max(t for t in changes if t is not None).timestamp())


def calendar_feed(request, feed_token: str) -> HttpResponse:
    feed = FeedToken.objects.select_related("calendar", "user").filter(token=feed_token).first()
    if feed is None:
        return HttpResponse("Calendar not found", status=404, content_type="text/plain")
    # The URL is the user's: it works only while they may still read the calendar. Once they may not,
    # it is gone for good (lost through a group, say), also if they get access again later.
    if not feed.user.is_active or get_membership(feed.calendar, feed.user) is None:
        if feed.user.is_active:
            feed.delete()
        return HttpResponse("Calendar not found", status=404, content_type="text/plain")
    calendar = feed.calendar

    # Subscribers ask again with If-None-Match / If-Modified-Since and get 304 while nothing changed,
    # which is answered before the feed is built.
    etag, last_modified = _feed_version(calendar)
    response = get_conditional_response(request, etag=etag, last_modified=last_modified)
    if response is None:
        events = (
            Event.objects.filter(
                calendar=calendar,
                parent__isnull=True,
                status__in={EventStatus.CONFIRMED, EventStatus.APPROVED},
            )
            .select_related("category", "resource")
            .prefetch_related(Prefetch("overrides", queryset=Event.objects.select_related("category", "resource")))
        )
        body = build_calendar_feed(calendar, events).encode()
        response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["ETag"] = etag
    response["Last-Modified"] = http_date(last_modified)
    # The feed may change any time: caches keep it but ask before using it again.
    response["Cache-Control"] = "no-cache"
    return response
