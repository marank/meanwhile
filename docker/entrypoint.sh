#!/bin/sh
# Checks the production settings, applies the migrations (the task queue's included) and sets up
# the admin user of ADMIN_EMAIL, then starts the command (supervisord). A failure stops the
# container before any of its programs start.
set -e

python manage.py check --deploy --fail-level ERROR
python manage.py migrate --no-input
python manage.py ensure_admin

exec "$@"
