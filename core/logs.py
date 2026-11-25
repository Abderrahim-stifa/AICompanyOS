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
