"""Tests for multidisciplinary request planning."""
import unittest

from core.ai_agents import AGENTS
from core.request_planner import build_request_plan


class RequestPlannerTests(unittest.TestCase):
    def test_builds_software_request_plan(self):
        result = build_request_plan("أريد تطوير برنامج لإدارة المخزون")
        self.assertIn("software_engineering", result["routing"]["capabilities"])
        self.assertEqual(result["selected_agent"], "engineer")
        self.assertTrue(result["role_plan"]["steps"])

    def test_accepts_another_recommended_agent(self):
        result = build_request_plan(
            "أريد دراسة جدوى اقتصادية لمشروع جديد",
            agent_key="accountant",
        )
        self.assertEqual(result["selected_agent"], "accountant")
        self.assertTrue(result["capability_details"])

    def test_rejects_agent_outside_recommendations(self):
        with self.assertRaises(ValueError):
            build_request_plan("أريد تصور معماري لفيلا", agent_key="marketing")

    def test_unknown_request_uses_general_review_agents(self):
        result = build_request_plan("طلب جديد يحتاج إلى دراسة")
        self.assertEqual(result["routing"]["primary_capability"], "general_review")
        self.assertIn(result["selected_agent"], AGENTS)
        self.assertEqual(result["capability_details"], [])

    def test_plan_discloses_limits(self):
        result = build_request_plan("تصميم واجهة تطبيق")
        self.assertIn("لم يتم إنتاج", result["notice"])


if __name__ == "__main__":
    unittest.main()
