"""Tests for persistent system activity logs."""
import tempfile
import unittest
from pathlib import Path

from core.database import Database


class ActivityLogTests(unittest.TestCase):
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
