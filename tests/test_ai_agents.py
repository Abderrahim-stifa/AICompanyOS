"""Smoke tests for the seven role-based agents."""
import unittest

from core.ai_agents import AGENTS, run_agent


class RoleAgentTests(unittest.TestCase):
    def test_all_seven_agents_return_a_plan(self):
        self.assertEqual(len(AGENTS), 7)
        for key in AGENTS:
            with self.subTest(agent=key):
                result = run_agent(key, "إطلاق منصة لإدارة المشاريع")
                self.assertTrue(result["steps"])
                self.assertTrue(result["questions"])
                self.assertIn("Rule-based", result["mode"])

    def test_unknown_agent_is_rejected(self):
        with self.assertRaises(ValueError):
            run_agent("unknown", "مهمة تجريبية")

    def test_empty_brief_is_rejected(self):
        with self.assertRaises(ValueError):
            run_agent("ceo", "  ")


if __name__ == "__main__":
    unittest.main()
