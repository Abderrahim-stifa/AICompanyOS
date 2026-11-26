"""Idempotent SQLite bootstrap for the v0.1 role-agent foundation.

This module extends the existing database additively. It deliberately does not
replace the established pipeline `agents` table or the existing `activity`
table, and never drops user data.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from core.database import Database
from core.settings import DATA_DIR, SETTINGS_FILE, load_settings

ROLE_AGENTS = (
    ("ceo", "CEO Agent", "الرئيس التنفيذي", "نشط"),
    ("engineer", "Engineer Agent", "المهندس", "نشط"),
    ("marketing", "Marketing Agent", "التسويق", "انتظار"),
    ("research", "Research Agent", "البحث", "انتظار"),
    ("consultant", "Consultant Agent", "الاستشارات", "انتظار"),
    ("accountant", "Accountant Agent", "المحاسبة", "انتظار"),
    ("market_analyst", "Market Analyst Agent", "تحليل السوق", "انتظار"),
)

DEFAULT_SETTINGS = {
    "company_name": "AICompanyOS",
    "language": "ar",
    "dark_mode": True,
    "theme": "modern",
}


def _ensure_settings_file() -> dict:
    """Create settings.json if absent; preserve an existing valid user file."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if SETTINGS_FILE.exists():
        with SETTINGS_FILE.open(encoding="utf-8") as handle:
            current = json.load(handle)
        if not isinstance(current, dict):
            raise ValueError("data/settings.json must contain a JSON object")
        merged = {**DEFAULT_SETTINGS, **current}
    else:
        merged = dict(DEFAULT_SETTINGS)
    if not SETTINGS_FILE.exists():
        temporary = SETTINGS_FILE.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(SETTINGS_FILE)
    return merged


def initialize_database(db_path: str | None = None, seed: bool = True) -> str:
    """Initialize the existing application schema and additive v0.1 tables."""
    settings = load_settings()
    target = db_path or settings.db_path
    Database(target).init()

    conn = sqlite3.connect(target)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS role_agents (
                agent_key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'انتظار',
                tasks_count INTEGER NOT NULL DEFAULT 0 CHECK (tasks_count >= 0),
                last_activity TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                company_name TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'ar',
                dark_mode INTEGER NOT NULL DEFAULT 1,
                theme TEXT NOT NULL DEFAULT 'modern'
            );

            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                created_at TEXT
            );
            """
        )
        if seed:
            conn.executemany(
                """INSERT OR IGNORE INTO role_agents
                   (agent_key, name, role, status) VALUES (?, ?, ?, ?)""",
                ROLE_AGENTS,
            )
        config = _ensure_settings_file()
        conn.execute(
            """INSERT OR IGNORE INTO settings
               (id, company_name, language, dark_mode, theme)
               VALUES (1, ?, ?, ?, ?)""",
            (
                str(config["company_name"]),
                str(config["language"]),
                int(bool(config["dark_mode"])),
                str(config["theme"]),
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return target


def list_role_agents(db_path: str | None = None) -> list[dict]:
    """Return role-agent rows with live task counts and latest activity timestamps."""
    target = db_path or load_settings().db_path
    initialize_database(target)
    with sqlite3.connect(target) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT r.agent_key, r.name, r.role, r.status,
                   (SELECT COUNT(*) FROM tasks t WHERE t.agent = r.agent_key) AS tasks_count,
                   (SELECT MAX(a.created_at) FROM activity a
                    WHERE a.agent = r.agent_key) AS last_activity
            FROM role_agents r
            ORDER BY r.rowid
            """
        ).fetchall()
    return [dict(row) for row in rows]


def record_activity_log(action: str, db_path: str | None = None) -> None:
    """Append an application-level event to the dedicated v0.1 activity log."""
    if not isinstance(action, str) or not action.strip():
        raise ValueError("action must be a non-empty string")
    target = db_path or load_settings().db_path
    initialize_database(target)
    from datetime import datetime, timezone

    with sqlite3.connect(target) as conn:
        conn.execute(
            "INSERT INTO activity_logs (action, created_at) VALUES (?, ?)",
            (action.strip(), datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )


if __name__ == "__main__":
    print(f"AICompanyOS database ready: {initialize_database()}")


def load_ui_settings(db_path: str | None = None) -> dict:
    """Load persisted dashboard preferences from the settings table."""
    target = initialize_database(db_path)
    with sqlite3.connect(target) as conn:
        row = conn.execute(
            "SELECT company_name, language, dark_mode, theme FROM settings WHERE id = 1"
        ).fetchone()
    if row is None:
        return dict(DEFAULT_SETTINGS)
    return {
        "company_name": row[0],
        "language": row[1],
        "dark_mode": bool(row[2]),
        "theme": row[3],
    }


def save_ui_settings(values: dict, db_path: str | None = None) -> dict:
    """Validate and persist dashboard preferences to SQLite and settings.json."""
    if not isinstance(values, dict):
        raise TypeError("settings must be a dictionary")
    current = load_ui_settings(db_path)
    merged = {**current, **values}
    company_name = str(merged.get("company_name", "")).strip()
    language = str(merged.get("language", "ar")).strip().lower()
    theme = str(merged.get("theme", "modern")).strip().lower()
    if not company_name or len(company_name) > 100:
        raise ValueError("company_name must contain 1 to 100 characters")
    if language not in {"ar", "en"}:
        raise ValueError("language must be 'ar' or 'en'")
    if theme not in {"modern"}:
        raise ValueError("unsupported theme")
    normalized = {
        "company_name": company_name,
        "language": language,
        "dark_mode": bool(merged.get("dark_mode", True)),
        "theme": theme,
    }
    target = db_path or load_settings().db_path
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = SETTINGS_FILE.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(SETTINGS_FILE)
    with sqlite3.connect(target) as conn:
        conn.execute(
            """INSERT INTO settings (id, company_name, language, dark_mode, theme)
               VALUES (1, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 company_name=excluded.company_name,
                 language=excluded.language,
                 dark_mode=excluded.dark_mode,
                 theme=excluded.theme""",
            (company_name, language, int(normalized["dark_mode"]), theme),
        )
    return normalized
