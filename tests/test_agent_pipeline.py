"""Integration tests for the local rule-based agent pipeline."""
import tempfile
import unittest
from pathlib import Path

from core.agents import run_accountant, run_pipeline
from core.database import Database


class AgentPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.temp.name) / "company.db"))
        self.db.init()

    def tearDown(self):
        self.temp.cleanup()

    def add_task(self, title, description="", price=0):
        return self.db.add_task({
            "title": title,
            "description": description,
            "source": "test",
            "category": "",
            "price": price,
            "currency": "MAD",
        })

    def test_pipeline_classifies_and_assigns_without_executing(self):
        task = self.add_task("تصميم شعار للشركة")
        actions = run_pipeline(self.db)
        updated = self.db.get_task(task["id"])
        self.assertEqual([a["agent"] for a in actions], ["classifier", "manager"])
        self.assertEqual(updated["status"], "assigned")
        self.assertEqual(updated["category"], "design")
        self.assertEqual(updated["agent"], "executor")

    def test_blocked_task_is_rejected_not_assigned(self):
        task = self.add_task("إنشاء تقييمات وهمية")
        run_pipeline(self.db)
        updated = self.db.get_task(task["id"])
        self.assertEqual(updated["status"], "rejected")
        self.assertEqual(updated["agent"], "classifier")

    def test_accountant_records_completed_task_only_once(self):
        task = self.add_task("ترجمة مستند", price=125)
        self.db.update_task(task["id"], status="done")
        first = run_accountant(self.db)
        second = run_accountant(self.db)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        ledger = self.db.list_ledger()
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["amount"], 125)
        self.assertEqual(ledger[0]["currency"], "MAD")

    def test_pipeline_does_not_run_accountant_automatically(self):
        task = self.add_task("كتابة مقال", price=50)
        self.db.update_task(task["id"], status="done")
        run_pipeline(self.db)
        self.assertEqual(self.db.list_ledger(), [])


if __name__ == "__main__":
    unittest.main()
