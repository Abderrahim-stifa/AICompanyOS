"""Database backups using SQLite's online backup API (safe while the app is running)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
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


def restore_backup(backup_file: str, db_path: str) -> None:
    """Replace the database with a backup. The current DB is saved next to it first."""
    backup = Path(backup_file)
    if not backup.exists():
        raise FileNotFoundError(f"backup not found: {backup_file}")

    # Make sure the file really is a SQLite database before touching anything.
    check = sqlite3.connect(backup)
    try:
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("backup file is corrupted")
    finally:
        check.close()

    target = Path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        safety = target.with_name(f"{target.stem}.before-restore{SUFFIX}")
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(safety)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

    src = sqlite3.connect(backup)
    dst = sqlite3.connect(db_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    log.info("database restored from %s", backup.name)
