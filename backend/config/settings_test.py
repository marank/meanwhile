"""
Settings for the tests (pytest): development's, whatever .env says.
"""

import os

os.environ["ENVIRONMENT"] = "development"

from config.settings import *  # noqa: E402, F403

# Argon2 is slow on purpose; the tests hash a password for every user they make and check one at
# every CalDAV request. Which hasher is used isn't what they test.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# Nor is waiting before a wrong password is refused.
CALDAV_FAILED_LOGIN_DELAY = 0
