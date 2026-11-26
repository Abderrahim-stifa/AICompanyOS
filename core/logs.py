"""Logging setup: console + rotating file."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_configured = False


def setup_logging(log_dir: str, level: str = "INFO") -> None:
    """Configure the root 'aicos' logger once."""
    global _configured
    if _configured:
        return

    Path(log_dir).mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("aicos")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.propagate = False

    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        Path(log_dir) / "aicompanyos.log",
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"aicos.{name}")



def log_activity(database, action: str, entity_type: str, entity_id: int,
                 user_name: str, details: str = "") -> None:
    """Persist an audit event through the configured Database instance.

    Passing the database instance keeps audit writes on the same SQLite file
    as the application and avoids hard-coded developer-local paths.
    """
    if not isinstance(user_name, str) or not user_name.strip():
        raise ValueError("user_name must be a non-empty string")
    if not isinstance(action, str) or not action.strip():
        raise ValueError("action must be a non-empty string")
    database.add_system_log(
        action.strip(),
        details,
        entity_type=entity_type,
        entity_id=entity_id,
        user_name=user_name.strip(),
    )


class DatabaseActivityLogger:
    """Activity logger adapter implementing the service-layer logger contract."""

    def __init__(self, database):
        self.database = database

    def log(self, action, entity_type, entity_id, user_name, details=""):
        return log_activity(
            self.database, action=action, entity_type=entity_type,
            entity_id=entity_id, user_name=user_name, details=details,
        )
