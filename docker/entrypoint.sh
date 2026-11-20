#!/bin/sh
# Checks the production settings, then starts the command. For the app (supervisord) it first
# applies the migrations (the task queue's included) and sets up the admin user of ADMIN_EMAIL;
# the worker (docker/worker) waits for those instead of racing the app. A failure stops the
# container before any of its programs start.
set -e

python manage.py check --deploy --fail-level ERROR
if [ "${1:-}" = supervisord ]; then
  python manage.py migrate --no-input
  python manage.py ensure_admin
fi

exec "$@"
