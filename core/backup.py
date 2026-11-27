"""Database backups using SQLite's online backup API (safe while the app is running)."""
from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from .logs import get_logger

log = get_logger("backup")

PREFIX = "aicompanyos-"
SUFFIX = ".db"


def create_backup(db_path: str, backup_dir: str, keep: int = 10) -> Path:
    """Copy the database to backup_dir and prune old backups beyond `keep`."""
    source = Path(db_path)
    if not source.exists():
        raise FileNotFoundError(f"database not found: {db_path}")

    target_dir = Path(backup_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{PREFIX}{datetime.now():%Y%m%d-%H%M%S-%f}{SUFFIX}"

    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    log.info("backup created: %s", target)
    _prune(target_dir, keep)
    return target


def list_backups(backup_dir: str) -> list[Path]:
    """Backups sorted oldest -> newest."""
    return sorted(Path(backup_dir).glob(f"{PREFIX}*{SUFFIX}"))


def _prune(backup_dir: Path, keep: int) -> None:
    backups = list_backups(str(backup_dir))
    for old in backups[: max(0, len(backups) - max(1, keep))]:
        old.unlink()
        log.info("old backup removed: %s", old.name)



def auto_backup_if_needed(
    db_path: str,
    backup_dir: str,
    interval_hours: int = 24,
    *,
    now: datetime | None = None,
) -> Path | None:
    """Create a backup when none exists or the newest backup is at least N hours old.

    Returns the new backup path, or None when the existing backup is still fresh.
    The optional clock value makes scheduling deterministic in tests.
    """
    if not isinstance(interval_hours, int) or interval_hours <= 0:
        raise ValueError("interval_hours must be a positive integer")

    current_time = now or datetime.now()
    existing = list_backups(backup_dir)
    if existing:
        newest = max(existing, key=lambda path: path.stat().st_mtime)
        last_backup = datetime.fromtimestamp(newest.stat().st_mtime)
        if current_time - last_backup < timedelta(hours=interval_hours):
            log.debug("automatic backup skipped; latest backup is still fresh")
            return None

    return create_backup(db_path, backup_dir)


def inspect_backup(backup_file: str) -> dict:
    """Validate a SQLite backup and return safe metadata for a restore preview."""
    backup = Path(backup_file)
    if not backup.is_file():
        raise FileNotFoundError(f"backup not found: {backup_file}")
    try:
        check = sqlite3.connect(f"file:{backup.resolve().as_posix()}?mode=ro", uri=True)
        try:
            integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ValueError("backup file is corrupted")
            tables = [
                row[0] for row in check.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
            ]
        finally:
            check.close()
    except sqlite3.DatabaseError:
        raise ValueError("backup file is not a readable SQLite database") from None
    stat = backup.stat()
    return {
        "name": backup.name,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
        "integrity": integrity,
        "tables": tables,
    }


def restore_backup(backup_file: str, db_path: str) -> Path | None:
    """Atomically restore a validated backup after preserving the active database."""
    backup = Path(backup_file)
    inspect_backup(str(backup))

    target = Path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    safety = None
    if target.exists():
        safety = target.with_name(
            f"{target.stem}.before-restore-{datetime.now():%Y%m%d-%H%M%S-%f}{SUFFIX}"
        )
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(safety)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target.stem}.restore-", suffix=SUFFIX, dir=target.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        src = sqlite3.connect(backup)
        dst = sqlite3.connect(temporary)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        check = sqlite3.connect(temporary)
        try:
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("restored database failed integrity check")
        finally:
            check.close()
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()

    log.info("database restored from %s", backup.name)
    return safety
