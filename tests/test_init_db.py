"""Tests for additive and repeatable v0.1 database initialization."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import init_db


class InitDatabaseTests(unittest.TestCase):
    def test_initialization_is_idempotent_and_preserves_pipeline_agents(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "company.sqlite3")
            settings_path = Path(directory) / "settings.json"
            with patch.object(init_db, "SETTINGS_FILE", settings_path):
                init_db.initialize_database(db_path)
                init_db.initialize_database(db_path)

            with sqlite3.connect(db_path) as conn:
                role_agents = conn.execute("SELECT agent_key FROM role_agents").fetchall()
                pipeline_agents = conn.execute("SELECT name FROM agents").fetchall()
                self.assertEqual(len(role_agents), 7)
                self.assertEqual(len(pipeline_agents), 5)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM activity_logs").fetchone()[0], 0)

            config = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(config["company_name"], "AICompanyOS")
            self.assertTrue(config["dark_mode"])

    def test_helpers_return_live_counts_and_record_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "company.sqlite3")
            settings_path = Path(directory) / "settings.json"
            with patch.object(init_db, "SETTINGS_FILE", settings_path):
                init_db.initialize_database(db_path)
                with sqlite3.connect(db_path) as conn:
                    conn.execute(
                        "INSERT INTO tasks (title, agent, created_at, updated_at) VALUES (?, ?, ?, ?)",
                        ("Prototype", "ceo", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
                    )
                    conn.execute(
                        "INSERT INTO activity (agent, action, created_at) VALUES (?, ?, ?)",
                        ("ceo", "reviewed plan", "2026-01-02T00:00:00+00:00"),
                    )
                agents = init_db.list_role_agents(db_path)
                ceo = next(agent for agent in agents if agent["agent_key"] == "ceo")
                self.assertEqual(ceo["tasks_count"], 1)
                self.assertEqual(ceo["last_activity"], "2026-01-02T00:00:00+00:00")
                init_db.record_activity_log("bootstrap complete", db_path)
                with sqlite3.connect(db_path) as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM activity_logs").fetchone()[0], 1)

    def test_ui_preferences_round_trip_to_json_and_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "company.sqlite3")
            settings_path = Path(directory) / "settings.json"
            with patch.object(init_db, "SETTINGS_FILE", settings_path):
                init_db.initialize_database(db_path)
                saved = init_db.save_ui_settings({
                    "company_name": "شركة الاختبار",
                    "language": "ar",
                    "dark_mode": False,
                    "theme": "modern",
                }, db_path)
                loaded = init_db.load_ui_settings(db_path)
            self.assertEqual(saved, loaded)
            self.assertEqual(loaded["company_name"], "شركة الاختبار")
            self.assertFalse(loaded["dark_mode"])
            file_data = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(file_data["company_name"], "شركة الاختبار")
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT company_name, language, dark_mode FROM settings WHERE id = 1"
                ).fetchone()
            self.assertEqual(row, ("شركة الاختبار", "ar", 0))

    def test_invalid_ui_preferences_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "company.sqlite3")
            with patch.object(init_db, "SETTINGS_FILE", Path(directory) / "settings.json"):
                init_db.initialize_database(db_path)
                with self.assertRaises(ValueError):
                    init_db.save_ui_settings({"company_name": " "}, db_path)
                with self.assertRaises(ValueError):
                    init_db.save_ui_settings({"language": "fr"}, db_path)

    def test_existing_settings_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "company.sqlite3")
            settings_path = Path(directory) / "settings.json"
            settings_path.write_text(
                json.dumps({"company_name": "My Company", "language": "en"}),
                encoding="utf-8",
            )
            with patch.object(init_db, "SETTINGS_FILE", settings_path):
                init_db.initialize_database(db_path)
            saved = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["company_name"], "My Company")
            self.assertEqual(saved["language"], "en")


if __name__ == "__main__":
    unittest.main()
