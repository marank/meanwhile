"""
URL configuration for the Calendar backend.
"""

from allauth.headless.constants import Client
from allauth.headless.urls import build_urlpatterns
from django.contrib import admin
from django.urls import include, path, re_path

from core.api import api
from core.views.auth import csrf_view
from core.views.dav import well_known_caldav
from core.views.feed import calendar_feed

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/csrf/", csrf_view),
    path(
        "api/auth/",
        include((build_urlpatterns(Client.BROWSER), "headless"), namespace="browser"),
    ),
    path("api/", api.urls),
    path("ics/<str:feed_token>.ics", calendar_feed),
    re_path(r"^\.well-known/caldav/?$", well_known_caldav),
]
