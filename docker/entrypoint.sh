#!/bin/sh
# Applies the migrations (the task queue's included) and sets up the admin user of ADMIN_EMAIL,
# then starts the command (supervisord).
set -e

python manage.py migrate --no-input
python manage.py ensure_admin

exec "$@"
