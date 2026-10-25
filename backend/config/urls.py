"""
URL configuration for the Calendar backend.
"""

from allauth.headless.constants import Client
from allauth.headless.urls import build_urlpatterns
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

from core.api import api
from core.views.auth import csrf_view
from core.views.dav import well_known_caldav
from core.views.feed import calendar_feed

urlpatterns = [
    path("api/auth/csrf", csrf_view),
    path(
        "api/auth/",
        include((build_urlpatterns(Client.BROWSER), "headless"), namespace="browser"),
    ),
    path("api/", api.urls),
    path("ics/<str:feed_token>.ics", calendar_feed),
    re_path(r"^\.well-known/caldav/?$", well_known_caldav),
]

# Not under /admin, which is the app's own administration page. Defense in depth: nginx also
# answers /django-admin with 404 when ADMIN_ENABLED is false.
if settings.ADMIN_ENABLED:
    urlpatterns.insert(0, path("django-admin/", admin.site.urls))
