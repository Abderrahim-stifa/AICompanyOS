"""Persistence and approval-gate tests for role-agent runs."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.database import Database
from core.validator import ValidationError


class RoleAgentRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.temp.name) / "company.db"))
        self.db.init()
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS role_agents (
                    agent_key TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'انتظار',
                    tasks_count INTEGER NOT NULL DEFAULT 0,
                    last_activity TEXT
                )"""
            )
            conn.execute(
                "INSERT INTO role_agents (agent_key, name, role) VALUES (?, ?, ?)",
                ("engineer", "Engineer Agent", "Engineering"),
            )
        self.task = self.db.add_task({
            "title": "Build a landing page",
            "description": "Create and test a responsive landing page",
            "source": "test",
            "category": "programming",
            "price": 0,
            "currency": "MAD",
        })
        self.db.assign_role_agent(self.task["id"], "engineer", "tester")
        self.plan = {
            "agent": "Engineer Agent",
            "title": "Engineering plan",
            "brief": "Build a landing page",
            "steps": ["Design", "Implement", "Test"],
            "mode": "Rule-based / Offline",
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_new_run_waits_for_human_approval_and_persists_plan(self):
        run = self.db.create_role_agent_run(
            self.task["id"], "engineer", self.plan, requested_by="alice"
        )
        self.assertEqual(run["status"], "awaiting_approval")
        self.assertEqual(run["plan"], self.plan)
        self.assertEqual(run["requested_by"], "alice")
        self.assertEqual(self.db.list_role_agent_runs(self.task["id"])[0]["id"], run["id"])

    def test_cannot_create_run_for_unassigned_or_different_agent(self):
        with self.assertRaises(ValidationError):
            self.db.create_role_agent_run(self.task["id"], "research", self.plan)

    def test_result_requires_approval(self):
        run = self.db.create_role_agent_run(self.task["id"], "engineer", self.plan)
        with self.assertRaises(ValidationError):
            self.db.complete_role_agent_run(run["id"], "Done", "alice")

    def test_approval_then_manual_result_completes_run_and_audits(self):
        run = self.db.create_role_agent_run(self.task["id"], "engineer", self.plan)
        approved = self.db.review_role_agent_run(run["id"], "approved", "manager")
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["reviewed_by"], "manager")
        completed = self.db.complete_role_agent_run(run["id"], "Implemented and tested.", "alice")
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["result"], "Implemented and tested.")
        logs = self.db.list_system_logs(limit=100)
        actions = [row["action"] for row in logs]
        self.assertIn("AGENT_PLAN_CREATED", actions)
        self.assertIn("AGENT_PLAN_REVIEWED", actions)
        self.assertIn("AGENT_RUN_COMPLETED", actions)

    def test_rejected_run_cannot_be_completed_or_re_reviewed(self):
        run = self.db.create_role_agent_run(self.task["id"], "engineer", self.plan)
        rejected = self.db.review_role_agent_run(run["id"], "rejected", "manager")
        self.assertEqual(rejected["status"], "rejected")
        with self.assertRaises(ValidationError):
            self.db.complete_role_agent_run(run["id"], "Not run", "alice")
        with self.assertRaises(ValidationError):
            self.db.review_role_agent_run(run["id"], "approved", "manager")

    def test_invalid_decision_and_empty_result_are_rejected(self):
        run = self.db.create_role_agent_run(self.task["id"], "engineer", self.plan)
        with self.assertRaises(ValidationError):
            self.db.review_role_agent_run(run["id"], "run_now", "manager")
        self.db.review_role_agent_run(run["id"], "approved", "manager")
        with self.assertRaises(ValidationError):
            self.db.complete_role_agent_run(run["id"], "  ", "alice")


if __name__ == "__main__":
    unittest.main()
