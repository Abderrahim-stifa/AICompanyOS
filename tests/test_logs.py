"""Tests for persistent system activity logs."""
import tempfile
import unittest
from pathlib import Path

from core.database import Database


class ActivityLogTests(unittest.TestCase):
    def test_legacy_activity_log_schema_is_migrated_without_losing_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "legacy.db")
            import sqlite3
            with sqlite3.connect(path) as conn:
                conn.execute("""
                    CREATE TABLE activity_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        action TEXT NOT NULL,
                        details TEXT NOT NULL DEFAULT '',
                        created_at TEXT
                    )
                """)
                conn.execute(
                    "INSERT INTO activity_logs (action, details, created_at) VALUES (?, ?, ?)",
                    ("OLD_EVENT", "preserve me", "2026-01-01T00:00:00"),
                )
            db = Database(path)
            db.init()
            old = db.list_system_logs()[0]
            self.assertEqual(old["action"], "OLD_EVENT")
            self.assertEqual(old["details"], "preserve me")
            self.assertEqual(old["user_name"], "system")
            self.assertIsNone(old["entity_type"])
            self.assertIsNone(old["entity_id"])

    def test_log_table_and_task_events(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(str(Path(directory) / "company.db"))
            db.init()
            with db.connect() as conn:
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='activity_logs'"
                ).fetchone()
            self.assertIsNotNone(exists)

            task = db.add_task({
                "title": "Audit logs", "description": "", "source": "",
                "category": "", "price": 0, "currency": "MAD",
            })
            entries = db.list_system_logs()
            self.assertEqual(entries[0]["action"], "CREATE")
            self.assertEqual(entries[0]["entity_type"], "TASK")
            self.assertEqual(entries[0]["entity_id"], task["id"])
            self.assertEqual(entries[0]["user_name"], "Admin")
            self.assertEqual(entries[0]["details"], "Audit logs")
            self.assertTrue(entries[0]["created_at"])


if __name__ == "__main__":
    unittest.main()
