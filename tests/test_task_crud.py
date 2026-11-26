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
        task = self.add_task()
        self.db.update_task(task["id"], title="Renamed")
        self.db.delete_task(task["id"])
        logs = self.db.list_system_logs()
        self.assertEqual([row["action"] for row in logs],
                         ["DELETE_TASK", "UPDATE_TASK", "CREATE_TASK"])
        self.assertIn("Renamed", logs[1]["details"])

    def test_invalid_priority_is_rejected(self):
        task = self.add_task()
        with self.assertRaises(ValueError):
            self.db.update_task(task["id"], priority="critical")


if __name__ == "__main__":
    unittest.main()
