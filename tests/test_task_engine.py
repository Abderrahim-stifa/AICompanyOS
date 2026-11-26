"""Tests for the v0.2 role-agent task engine and additive schema migration."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.database import Database
from core.validator import ValidationError


class RoleAgentTaskEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "company.sqlite3")
        self.db = Database(self.path)
        self.db.init()
        with sqlite3.connect(self.path) as conn:
            conn.execute("""
                CREATE TABLE role_agents (
                    agent_key TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'انتظار'
                )
            """)
            conn.execute(
                "INSERT INTO role_agents (agent_key, name, role) VALUES (?, ?, ?)",
                ("engineer", "Engineer Agent", "المهندس"),
            )
        self.task = self.db.add_task({
            "title": "Build feature",
            "description": "Implement a small feature",
            "source": "test",
            "category": "engineering",
            "price": 0,
            "currency": "MAD",
        })

    def tearDown(self):
        self.temp.cleanup()

    def test_schema_migration_preserves_pipeline_agent_and_adds_role_fields(self):
        with self.db.connect() as conn:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
        self.assertTrue({"agent", "role_agent_key", "result", "assigned_at", "completed_at"} <= columns)
        updated = self.db.update_task(self.task["id"], agent="executor")
        self.assertEqual(updated["agent"], "executor")

    def test_assign_role_agent_records_assignment_and_activity(self):
        assigned = self.db.assign_role_agent(self.task["id"], "engineer", user_name="Operator")
        self.assertEqual(assigned["role_agent_key"], "engineer")
        self.assertEqual(assigned["status"], "assigned")
        self.assertIsNotNone(assigned["assigned_at"])
        activity = self.db.list_activity()
        self.assertEqual(activity[0]["agent"], "engineer")
        self.assertEqual(activity[0]["task_id"], self.task["id"])
        audit = self.db.list_system_logs()[0]
        self.assertEqual((audit["action"], audit["entity_type"], audit["entity_id"], audit["user_name"]),
                         ("ASSIGN", "TASK", self.task["id"], "Operator"))
        unassigned = self.db.unassign_role_agent(self.task["id"], user_name="Operator")
        self.assertIsNone(unassigned["role_agent_key"])
        self.assertEqual(self.db.list_system_logs()[0]["action"], "UNASSIGN")

    def test_unknown_role_agent_is_rejected(self):
        with self.assertRaises(LookupError):
            self.db.assign_role_agent(self.task["id"], "not-real")

    def test_save_result_completes_task_and_persists_output(self):
        self.db.assign_role_agent(self.task["id"], "engineer")
        updated = self.db.save_task_result(self.task["id"], "Implementation report")
        self.assertEqual(updated["result"], "Implementation report")
        self.assertEqual(updated["status"], "done")
        self.assertIsNotNone(updated["completed_at"])
        self.assertEqual(self.db.list_activity()[0]["action"], "تم حفظ نتيجة تنفيذ المهمة")

    def test_empty_result_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.db.save_task_result(self.task["id"], "  ")

    def test_status_transition_is_validated_and_logged(self):
        updated = self.db.set_task_status(self.task["id"], "in_progress")
        self.assertEqual(updated["status"], "in_progress")
        self.assertIsNone(updated["completed_at"])
        with self.assertRaises(ValidationError):
            self.db.set_task_status(self.task["id"], "unknown")


if __name__ == "__main__":
    unittest.main()
