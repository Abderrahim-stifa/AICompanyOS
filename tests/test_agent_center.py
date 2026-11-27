"""Tests for the seven-role Agent Center overview."""
import unittest

from core.agent_center import build_agent_overview


class AgentCenterTests(unittest.TestCase):
    def test_all_seven_agents_are_returned_even_without_tasks(self):
        result = build_agent_overview([])
        self.assertEqual(len(result), 7)
        self.assertTrue(all(row["task_count"] == 0 for row in result))
        self.assertTrue(all(row["status"] == "ready" for row in result))

    def test_counts_tasks_and_active_status(self):
        result = build_agent_overview([
            {"agent": "ceo", "status": "in_progress"},
            {"agent": "CEO Agent", "status": "done"},
            {"agent": "research", "status": "assigned"},
            {"agent": "manager", "status": "in_progress"},
        ])
        by_key = {row["key"]: row for row in result}
        self.assertEqual(by_key["ceo"]["task_count"], 2)
        self.assertEqual(by_key["ceo"]["active_task_count"], 1)
        self.assertEqual(by_key["ceo"]["completed_task_count"], 1)
        self.assertEqual(by_key["ceo"]["status"], "active")
        self.assertEqual(by_key["research"]["active_task_count"], 1)
        self.assertEqual(by_key["research"]["status"], "active")
        # Pipeline agent is not included in any role-agent count.
        self.assertEqual(sum(row["task_count"] for row in result), 3)

    def test_canonical_role_assignment_is_counted_not_pipeline_agent(self):
        result = build_agent_overview([
            {"agent": "executor", "role_agent_key": "engineer", "status": "assigned"},
            {"agent": "manager", "role_agent_key": None, "status": "in_progress"},
        ])
        by_key = {row["key"]: row for row in result}
        self.assertEqual(by_key["engineer"]["task_count"], 1)
        self.assertEqual(by_key["engineer"]["active_task_count"], 1)
        self.assertEqual(sum(row["task_count"] for row in result), 1)

    def test_disabled_agent_status_has_priority(self):
        result = build_agent_overview(
            [{"agent": "engineer", "status": "in_progress"}],
            enabled={"engineer": False},
        )
        engineer = next(row for row in result if row["key"] == "engineer")
        self.assertEqual(engineer["status"], "disabled")
        self.assertFalse(engineer["enabled"])


if __name__ == "__main__":
    unittest.main()
