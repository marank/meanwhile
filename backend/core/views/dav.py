"""
CalDAV service discovery (RFC 6764).
"""

from django.conf import settings
from django.http import HttpResponsePermanentRedirect
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def well_known_caldav(request):
    # Clients ask with PROPFIND as well as GET, so every method is redirected to the CalDAV root.
    return HttpResponsePermanentRedirect(settings.CALDAV_PATH.rstrip("/") + "/")
