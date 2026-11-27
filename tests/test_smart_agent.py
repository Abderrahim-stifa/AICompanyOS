"""Tests for offline smart task analysis and pipeline integration."""
import tempfile
import unittest
from pathlib import Path

from core.agents import run_classifier
from core.database import Database
from core.smart_agent import SmartTaskAnalyzer


class SmartTaskAnalyzerTests(unittest.TestCase):
    def test_detects_programming_and_urgent_priority(self):
        result = SmartTaskAnalyzer.analyze_and_classify("عاجل: إصلاح bug في تطبيق Python اليوم")
        self.assertEqual(result["category"], "programming")
        self.assertEqual(result["priority"], "urgent")
        self.assertEqual(result["suggested_agent"], "executor")
        self.assertEqual(result["suggested_role_agent"], "engineer")

    def test_detects_accounting_and_high_priority(self):
        result = SmartTaskAnalyzer.analyze_and_classify("مهم هذا الأسبوع: مراجعة فاتورة وراتب الموظفين")
        self.assertEqual(result["category"], "accounting")
        self.assertEqual(result["priority"], "high")
        self.assertEqual(result["suggested_agent"], "accountant")
        self.assertEqual(result["suggested_role_agent"], "accountant")

    def test_unknown_text_defaults_to_general_and_normal(self):
        result = SmartTaskAnalyzer.analyze_and_classify("متابعة موضوع جديد")
        self.assertEqual(result["category"], "general")
        self.assertEqual(result["priority"], "normal")
        self.assertEqual(result["suggested_agent"], "classifier")
        self.assertEqual(result["suggested_role_agent"], "consultant")

    def test_pipeline_persists_inferred_category_and_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(str(Path(directory) / "company.db"))
            db.init()
            task = db.add_task({
                "title": "إطلاق حملة تسويق عاجلة",
                "description": "نحتاج إطلاق إعلان اليوم",
                "source": "test",
                "category": "",
                "price": 0,
                "currency": "MAD",
            })
            run_classifier(db)
            updated = db.get_task(task["id"])
            self.assertEqual(updated["category"], "marketing")
            self.assertEqual(updated["priority"], "urgent")
            events = db.list_activity()
            self.assertTrue(any("الوكيل المتخصص المقترح: marketing" in row["action"] for row in events))


if __name__ == "__main__":
    unittest.main()
