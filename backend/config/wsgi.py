"""
WSGI entry point, used by Django's own tooling only. The app is served through ASGI (config/asgi.py),
which also mounts the CalDAV server.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
