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
            """INSERT OR IGNORE INTO app_settings
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


if __name__ == "__main__":
    print(f"AICompanyOS database ready: {initialize_database()}")
