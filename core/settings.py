"""Application settings.

Values come from (lowest to highest priority):
1. built-in defaults
2. data/settings.json (optional)
3. environment variables prefixed with AICOS_ (e.g. AICOS_PORT=9000)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, fields
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("AICOS_DATA_DIR", BASE_DIR / "data"))
SETTINGS_FILE = DATA_DIR / "settings.json"


@dataclass
class Settings:
    db_path: str = str(DATA_DIR / "aicompanyos.db")
    log_dir: str = str(DATA_DIR / "logs")
    log_level: str = "INFO"
    backup_dir: str = str(DATA_DIR / "backups")
    backup_keep: int = 10
    host: str = "127.0.0.1"
    port: int = 8000
    default_currency: str = "USD"
    # Optional API key for the HTTP API. Empty = no authentication (local use only).
    api_key: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _coerce(value: str, default):
    """Convert an environment string to the type of the default value."""
    if isinstance(default, bool):
        return value.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        return int(value)
    return value


def load_settings() -> Settings:
    settings = Settings()
    valid = {f.name for f in fields(Settings)}

    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, encoding="utf-8") as fh:
            for key, value in json.load(fh).items():
                if key in valid:
                    setattr(settings, key, value)

    for name in valid:
        env = os.environ.get(f"AICOS_{name.upper()}")
        if env is not None:
            setattr(settings, name, _coerce(env, getattr(settings, name)))

    return settings


def save_settings(settings: Settings) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
        json.dump(settings.to_dict(), fh, indent=2, ensure_ascii=False)
