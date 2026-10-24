"""
Settings for the tests (pytest): development's, whatever .env says.
"""

import os

os.environ["ENVIRONMENT"] = "development"

from config.settings import *  # noqa: E402, F403
