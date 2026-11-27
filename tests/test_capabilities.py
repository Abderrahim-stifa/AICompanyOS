"""Tests for the multidisciplinary capability catalog and router."""
import unittest

from core.capabilities import CAPABILITIES, get_capability_catalog, route_request


class CapabilityRoutingTests(unittest.TestCase):
    def test_catalog_covers_requested_domains(self):
        expected = {
            "software_engineering",
            "visual_design",
            "architectural_concepts",
            "feasibility_studies",
            "research_problem_solving",
            "business_operations",
        }
        self.assertEqual(set(CAPABILITIES), expected)
        self.assertEqual({item["key"] for item in get_capability_catalog()}, expected)

    def test_routes_software_request(self):
        result = route_request("أريد تطوير برنامج لإدارة المخزون مع قاعدة بيانات")
        self.assertEqual(result["primary_capability"], "software_engineering")
        self.assertIn("engineer", result["recommended_agents"])

    def test_routes_architectural_request(self):
        result = route_request("أحتاج تصور معماري لفيلا وتوزيع الغرف")
        self.assertIn("architectural_concepts", result["capabilities"])

    def test_routes_feasibility_and_research(self):
        result = route_request("أريد دراسة جدوى اقتصادية وتحليل التكاليف ونقطة التعادل")
        self.assertEqual(result["primary_capability"], "feasibility_studies")
        self.assertIn("accountant", result["recommended_agents"])

    def test_unknown_request_requires_review(self):
        result = route_request("موضوع جديد يحتاج إلى توضيح")
        self.assertEqual(result["primary_capability"], "general_review")
        self.assertEqual(result["capabilities"], [])

    def test_short_brief_is_rejected(self):
        with self.assertRaises(ValueError):
            route_request("abc")

    def test_router_discloses_rule_based_mode(self):
        result = route_request("تصميم واجهة تطبيق")
        self.assertIn("Rule-based", result["mode"])
        self.assertIn("ليس", result["notice"])


if __name__ == "__main__":
    unittest.main()
