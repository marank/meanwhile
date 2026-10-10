"""
Public iCal feed view.
"""

from django.http import HttpResponse

from core.models import Calendar, Event
from core.models.base import EventStatus
from core.services.ical import build_calendar_feed


def calendar_feed(request, feed_token: str) -> HttpResponse:
    try:
        calendar = Calendar.objects.get(feed_token=feed_token)
    except Calendar.DoesNotExist:
        return HttpResponse("Calendar not found", status=404, content_type="text/plain")

    events = Event.objects.filter(
        calendar=calendar,
        status__in={EventStatus.CONFIRMED, EventStatus.APPROVED},
    )
    body = build_calendar_feed(events)
    return HttpResponse(body, content_type="text/calendar")
