"""Tests for supervised domain-specific draft generation and provenance."""
import unittest

from core.deliverable_drafts import generate_domain_draft
from core.llm_provider import ProviderError


class FakeProvider:
    name = "fake-llm"
    model = "test-model"

    def generate(self, brief):
        return {
            "summary": "مسودة أولية",
            "deliverables": ["وثيقة المتطلبات"],
            "assumptions": ["توفر الميزانية"],
            "risks": ["تغير النطاق"],
            "questions": ["ما الموعد النهائي؟"],
            "provenance": {"source": "mock"},
        }


class BrokenProvider:
    name = "openai"
    model = "test-model"

    def generate(self, brief):
        raise ProviderError("تعذر الاتصال بمزود LLM أو انتهت مهلة الاتصال.")


class DomainDraftTests(unittest.TestCase):
    def test_generates_reviewable_draft_for_every_domain(self):
        for domain in ("software", "design", "architecture", "feasibility"):
            with self.subTest(domain=domain):
                draft = generate_domain_draft(domain, "أحتاج إعداد وثيقة أولية للمشروع", FakeProvider())
                self.assertEqual(draft["domain"], domain)
                self.assertEqual(draft["title"], "مسودة أولية")
                self.assertIn("## المخرجات المقترحة", draft["content"])
                self.assertIn("## المخاطر", draft["content"])
                self.assertEqual(draft["assumptions"], ["توفر الميزانية"])
                self.assertEqual(draft["metadata"]["provider"], "fake-llm")
                self.assertEqual(draft["metadata"]["model"], "test-model")
                self.assertEqual(draft["metadata"]["verification"], "not_verified")
                self.assertTrue(draft["metadata"]["requires_human_approval"])
                self.assertFalse(draft["metadata"]["approved"])
                self.assertFalse(draft["metadata"]["execution_performed"])

    def test_architecture_and_feasibility_have_specific_safety_boundaries(self):
        architecture = generate_domain_draft("architecture", "تصور أولي لمبنى", FakeProvider())
        feasibility = generate_domain_draft("feasibility", "دراسة جدوى أولية", FakeProvider())
        self.assertIn("ليس مخططاً تنفيذياً", architecture["content"])
        self.assertIn("افتراضات تحتاج", feasibility["content"])

    def test_software_and_design_boundaries_are_explicit(self):
        software = generate_domain_draft("software", "مواصفات تطبيق", FakeProvider())
        design = generate_domain_draft("design", "هوية بصرية", FakeProvider())
        self.assertIn("ليست كوداً إنتاجياً", software["content"])
        self.assertIn("ليست ملفات أصول نهائية", design["content"])

    def test_remote_provider_failure_uses_supervised_offline_fallback(self):
        draft = generate_domain_draft("software", "مواصفات منصة", BrokenProvider())
        self.assertEqual(draft["metadata"]["provider"], "offline")
        self.assertEqual(draft["metadata"]["requested_provider"], "openai")
        self.assertIn("fallback_reason", draft["metadata"])
        self.assertFalse(draft["metadata"]["approved"])

    def test_invalid_domain_and_empty_brief_are_rejected(self):
        with self.assertRaises(ValueError):
            generate_domain_draft("unknown", "وصف مشروع", FakeProvider())
        with self.assertRaises(ValueError):
            generate_domain_draft("software", " ", FakeProvider())


if __name__ == "__main__":
    unittest.main()
