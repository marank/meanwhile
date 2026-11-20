"""Database dumps into ``settings.BACKUP_DIR``, nightly by the ``backup_database`` job.

``pg_dump`` writes PostgreSQL's custom format (restore with ``pg_restore``) to
``<database>-<UTC timestamp>.dump``; dumps older than ``BACKUP_KEEP_DAYS`` days are
deleted after each successful dump.
"""

import logging
import os
import subprocess
import time
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)

# A dump that is still ".partial" after this long belongs to a dump that died.
STALE_PARTIAL_SECONDS = 3600


class BackupError(Exception):
    """pg_dump failed; the message is its error output."""


def available() -> bool:
    """Dumps need PostgreSQL; native development on SQLite has none."""
    return connection.vendor == "postgresql"


def backup_database() -> Path:
    """Dump the database into ``BACKUP_DIR`` now and return the new file."""
    database = connection.settings_dict
    directory = Path(settings.BACKUP_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{database['NAME']}-{timezone.now():%Y%m%dT%H%M%SZ}.dump"
    # Written under a temporary name first, so a failed dump never looks like a valid one.
    partial = target.with_name(f"{target.name}.partial")
    environment = {
        **os.environ,
        "PGHOST": str(database["HOST"]),
        "PGPORT": str(database["PORT"]),
        "PGDATABASE": str(database["NAME"]),
        "PGUSER": str(database["USER"]),
        "PGPASSWORD": str(database["PASSWORD"]),
    }
    try:
        # umask: the dump holds every password hash and personal record.
        subprocess.run(
            ["pg_dump", "--format=custom", f"--file={partial}"],
            env=environment,
            umask=0o077,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        partial.unlink(missing_ok=True)
        raise BackupError(error.stderr.strip() or f"pg_dump exited with {error.returncode}") from error
    partial.rename(target)
    logger.info("Database dumped to %s", target)
    remove_old_backups(directory)
    return target


def remove_old_backups(directory: Path) -> list[Path]:
    """Delete dumps older than ``BACKUP_KEEP_DAYS`` days and leftovers of failed dumps."""
    now = time.time()
    keep_after = now - settings.BACKUP_KEEP_DAYS * 86400
    removed = [path for path in directory.glob("*.dump") if path.stat().st_mtime < keep_after]
    removed += [path for path in directory.glob("*.partial") if path.stat().st_mtime < now - STALE_PARTIAL_SECONDS]
    for path in removed:
        path.unlink()
        logger.info("Removed old backup %s", path)
    return sorted(removed)
