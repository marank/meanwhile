"""
Nightly database dumps by the worker (apps.core.services.backups, the backup_database job and command).
pg_dump is replaced, so these run on SQLite too.
"""

import os
import subprocess
import time
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import CommandError, call_command
from django.db import connection
from pytest_django.fixtures import Settings

from apps.core import tasks
from apps.core.services import backups

pytestmark = pytest.mark.django_db


@pytest.fixture
def backup_dir(tmp_path: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Path:
    settings.BACKUP_DIR = str(tmp_path)
    settings.BACKUP_KEEP_DAYS = 14
    monkeypatch.setattr(backups, "available", lambda: True)
    # The dump's file name; the test database's name is no file name on SQLite.
    monkeypatch.setitem(connection.settings_dict, "NAME", "meanwhile")
    return tmp_path


def fake_pg_dump(calls: list[list[str]], *, fails: bool = False) -> Any:
    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        target = Path(command[-1].removeprefix("--file="))
        target.write_bytes(b"PGDMP")
        if fails:
            raise subprocess.CalledProcessError(1, command, stderr="connection refused")
        return subprocess.CompletedProcess(command, 0)

    return run


def age(path: Path, days: float) -> None:
    then = time.time() - days * 86400
    os.utime(path, (then, then))


def test_a_dump_is_written_and_old_ones_are_removed(backup_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old = backup_dir / "meanwhile-20200101T000000Z.dump"
    old.write_bytes(b"old")
    age(old, 15)
    recent = backup_dir / "meanwhile-20990101T000000Z.dump"
    recent.write_bytes(b"recent")
    stale_partial = backup_dir / "died.dump.partial"
    stale_partial.write_bytes(b"")
    age(stale_partial, 1)
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", fake_pg_dump(calls))

    path = backups.backup_database()

    assert calls[0][:2] == ["pg_dump", "--format=custom"]
    assert path.exists()
    assert path.suffix == ".dump"
    assert path.read_bytes() == b"PGDMP"
    assert sorted(p.name for p in backup_dir.iterdir()) == sorted([path.name, recent.name])


def test_a_failed_dump_leaves_no_file(backup_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", fake_pg_dump([], fails=True))
    with pytest.raises(backups.BackupError, match="connection refused"):
        backups.backup_database()
    assert list(backup_dir.iterdir()) == []


def test_the_command_dumps_now(backup_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", fake_pg_dump([]))
    out = StringIO()
    call_command("backup_database", stdout=out)
    assert "Database dumped to" in out.getvalue()


def test_the_command_reports_a_failed_dump(backup_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", fake_pg_dump([], fails=True))
    with pytest.raises(CommandError, match="pg_dump failed"):
        call_command("backup_database")


def test_the_command_needs_a_backup_dir(backup_dir: Path, settings: Settings) -> None:
    settings.BACKUP_DIR = ""
    with pytest.raises(CommandError, match="BACKUP_DIR"):
        call_command("backup_database")


def test_the_command_refuses_without_postgresql(settings: Settings, tmp_path: Path) -> None:
    settings.BACKUP_DIR = str(tmp_path)
    if backups.available():
        pytest.skip("runs on PostgreSQL")
    with pytest.raises(CommandError, match="PostgreSQL"):
        call_command("backup_database")


@pytest.mark.parametrize(("utc_hour", "dumps"), [(0, True), (1, False), (23, False)])
def test_the_job_dumps_only_in_the_hour_of_backup_time(
    utc_hour: int, dumps: bool, settings: Settings, monkeypatch: pytest.MonkeyPatch, backup_dir: Path
) -> None:
    # 01:30 in Berlin (winter) is 00:30 UTC.
    settings.TIME_ZONE = "Europe/Berlin"
    calls: list[int] = []
    monkeypatch.setattr(backups, "backup_database", lambda: calls.append(1))
    tasks.backup_database(timestamp=int(datetime(2026, 1, 15, utc_hour, 30, tzinfo=UTC).timestamp()))
    assert calls == ([1] if dumps else [])


def test_the_job_does_nothing_without_a_backup_dir(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.BACKUP_DIR = ""
    settings.TIME_ZONE = "UTC"
    calls: list[int] = []
    monkeypatch.setattr(backups, "backup_database", lambda: calls.append(1))
    tasks.backup_database(timestamp=int(datetime(2026, 1, 15, 1, 30, tzinfo=UTC).timestamp()))
    assert calls == []
