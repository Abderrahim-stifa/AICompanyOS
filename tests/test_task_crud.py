"""Integration coverage for task CRUD and additive priority migration."""
import tempfile
import unittest
from pathlib import Path

from core.database import Database


class TaskCrudTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.temp.name) / "company.db"))
        self.db.init()

    def tearDown(self):
        self.temp.cleanup()

    def add_task(self, title="Task A"):
        return self.db.add_task({
            "title": title, "description": "Initial description",
            "source": "test", "category": "", "price": 0,
            "currency": "MAD",
        })

    def test_create_read_update_delete_and_priority(self):
        created = self.add_task()
        self.assertEqual(created["priority"], "normal")
        updated = self.db.update_task(
            created["id"], title="Task B", description="Updated",
            priority="high", status="assigned",
        )
        self.assertEqual(updated["title"], "Task B")
        self.assertEqual(updated["description"], "Updated")
        self.assertEqual(updated["priority"], "high")
        self.assertEqual(updated["status"], "assigned")
        self.assertEqual(self.db.get_tasks()[0]["title"], "Task B")
        self.db.delete_task(created["id"])
        self.assertEqual(self.db.list_tasks(), [])

    def test_create_update_delete_are_recorded(self):
        task = self.db.add_task({
            "title": "Audit me", "description": "", "source": "test",
            "category": "", "price": 0, "currency": "MAD",
        }, user_name="Tester")
        self.db.update_task(task["id"], title="Renamed", user_name="Editor")
        self.db.delete_task(task["id"], user_name="Owner")
        logs = self.db.list_system_logs()
        self.assertEqual([row["action"] for row in logs], ["DELETE", "UPDATE", "CREATE"])
        self.assertEqual(
            [(row["entity_type"], row["entity_id"], row["user_name"]) for row in logs],
            [("TASK", task["id"], "Owner"),
             ("TASK", task["id"], "Editor"),
             ("TASK", task["id"], "Tester")],
        )
        self.assertIn("Renamed", logs[1]["details"])

    def test_priority_column_migrates_existing_task_table(self):
        import sqlite3

        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "legacy.db")
            with sqlite3.connect(path) as conn:
                conn.execute("""
                    CREATE TABLE tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        source TEXT NOT NULL DEFAULT '',
                        category TEXT NOT NULL DEFAULT '',
                        price REAL NOT NULL DEFAULT 0,
                        currency TEXT NOT NULL DEFAULT 'USD',
                        status TEXT NOT NULL DEFAULT 'found',
                        agent TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                conn.execute(
                    "INSERT INTO tasks (title, created_at, updated_at) VALUES (?, ?, ?)",
                    ("Legacy task", "2026-01-01", "2026-01-01"),
                )
            migrated = Database(path)
            migrated.init()
            row = migrated.get_task(1)
            self.assertEqual(row["title"], "Legacy task")
            self.assertEqual(row["priority"], "normal")

    def test_invalid_priority_is_rejected(self):
        task = self.add_task()
        with self.assertRaises(ValueError):
            self.db.update_task(task["id"], priority="critical")


if __name__ == "__main__":
    unittest.main()


    def test_delete_task_audits_unlinking_of_invoice_and_payment_ledger(self):
        import json

        task = self.db.add_task({
            "title": "Financially linked task", "description": "", "source": "test",
            "category": "consulting", "price": 500, "currency": "MAD",
        }, user_name="Finance")
        invoice = self.db.create_invoice(task["id"], user_name="Finance")
        self.db.issue_invoice(invoice["id"], user_name="Finance")
        payment = self.db.record_payment(
            invoice["id"], 100, "MAD", "2026-11-27", user_name="Finance"
        )

        self.db.delete_task(task["id"], user_name="Owner")

        invoices = self.db.list_invoices()
        self.assertEqual(invoices[0]["id"], invoice["id"])
        self.assertIsNone(invoices[0]["task_id"])
        ledger = self.db.list_ledger()
        payment_ledger = next(row for row in ledger if row["id"] == payment["ledger_id"])
        self.assertIsNone(payment_ledger["task_id"])

        logs = self.db.list_system_logs()
        unlink_events = [row for row in logs if row["action"] == "UNLINK_TASK"]
        self.assertEqual(
            {(row["entity_type"], row["entity_id"]) for row in unlink_events},
            {("INVOICE", invoice["id"]), ("LEDGER", payment["ledger_id"])},
        )
        for event in unlink_events:
            self.assertEqual(event["user_name"], "Owner")
            self.assertEqual(json.loads(event["old_values"])["task_id"], task["id"])
            self.assertIsNone(json.loads(event["new_values"])["task_id"])
