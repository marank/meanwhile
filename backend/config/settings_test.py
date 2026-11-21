"""
Settings for the tests (pytest): development's (DEBUG), whatever .env says. SQLite natively,
PostgreSQL with DB_HOST (CI).
"""

import os

os.environ["DEBUG"] = "true"
# The app's address in links (emails, feeds), which the tests look for.
os.environ["APP_URLS"] = "http://app.test"

from config.settings import *  # noqa: F403

# Argon2 is slow on purpose; the tests hash a password for every user they make and check one at
# every CalDAV request. Which hasher is used isn't what they test.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# Nor is waiting before a wrong password is refused.
CALDAV_FAILED_LOGIN_DELAY = 0
# No nightly dumps from the tests.
BACKUP_DIR = ""
