#!/bin/sh
# Writes nginx's trusted proxies (TRUSTED_PROXIES), applies the migrations (the task queue's
# included) and sets up the admin user of ADMIN_EMAIL, then starts the command (supervisord).
set -e

trusted-proxies.sh
python manage.py migrate --no-input
python manage.py ensure_admin

exec "$@"
