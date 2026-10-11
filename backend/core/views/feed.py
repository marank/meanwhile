"""
Public iCal feed view.
"""

import hashlib

from django.db.models import Max
from django.http import HttpResponse
from django.utils.cache import get_conditional_response
from django.utils.http import http_date

from core.models import Calendar, DeletedEvent, Event
from core.models.base import EventStatus
from core.services.ical import build_calendar_feed


def calendar_feed(request, feed_token: str) -> HttpResponse:
    try:
        calendar = Calendar.objects.get(feed_token=feed_token)
    except Calendar.DoesNotExist:
        return HttpResponse("Calendar not found", status=404, content_type="text/plain")

    events = Event.objects.filter(
        calendar=calendar,
        parent__isnull=True,
        status__in={EventStatus.CONFIRMED, EventStatus.APPROVED},
    ).prefetch_related("overrides")
    body = build_calendar_feed(calendar, events).encode()

    # Subscribers ask again with If-None-Match / If-Modified-Since and get 304 while nothing changed.
    etag = f'"{hashlib.sha256(body).hexdigest()[:32]}"'
    changes = [
        calendar.updated_at,
        Event.objects.filter(calendar=calendar).aggregate(m=Max("updated_at"))["m"],
        DeletedEvent.objects.filter(calendar_id=calendar.id).aggregate(m=Max("deleted_at"))["m"],
    ]
    # Whole seconds, as HTTP dates have them.
    last_modified = int(max(t for t in changes if t is not None).timestamp())
    response = get_conditional_response(request, etag=etag, last_modified=last_modified)
    if response is None:
        response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["ETag"] = etag
    response["Last-Modified"] = http_date(last_modified)
    # The feed may change any time: caches keep it but ask before using it again.
    response["Cache-Control"] = "no-cache"
    return response
