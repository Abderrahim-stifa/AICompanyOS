"""Offline task analysis using transparent keyword heuristics.

This is deterministic rule-based classification, not a machine-learning model.
"""
from __future__ import annotations

import re
import unicodedata


CATEGORY_KEYWORDS = {
    "translation": ("ترجم", "ترجمة", "translate", "translation", "subtitle"),
    "programming": ("برمج", "كود", "code", "موقع", "تطبيق", "bug", "خطأ", "python", "api"),
    "marketing": ("تسويق", "إعلان", "اعلان", "سوشيال", "حملة", "marketing", "seo", "ads"),
    "accounting": ("فاتورة", "حساب", "مصروف", "راتب", "محاسبة", "invoice", "payroll"),
    "design": ("تصميم", "شعار", "هوية بصرية", "logo", "design", "banner"),
    "writing": ("كتابة", "نص", "مقال", "تلخيص", "تدقيق", "content", "article"),
    "data": ("بيانات", "تحليل", "إكسل", "اكسل", "excel", "spreadsheet", "csv"),
    "video": ("فيديو", "مونتاج", "video", "animation", "موشن"),
}

URGENCY_KEYWORDS = ("عاجل", "فوراً", "فورا", "مستعجل", "اليوم", "حالاً", "حالا", "asap", "urgent")
HIGH_PRIORITY_KEYWORDS = ("مهم", "أسبوع", "اسبوع", "قريباً", "قريبا", "هذا الأسبوع", "this week")

AGENT_BY_CATEGORY = {
    "translation": "finder",
    "programming": "executor",
    "marketing": "manager",
    "accounting": "accountant",
    "design": "executor",
    "writing": "executor",
    "data": "finder",
    "video": "executor",
    "general": "classifier",
}


def _normalize(value: str) -> str:
    """Normalize Arabic letter variants and whitespace for predictable matching."""
    value = unicodedata.normalize("NFKC", value or "").lower()
    value = re.sub(r"[\u064B-\u065F\u0670ـ]", "", value)
    value = value.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي"}))
    return re.sub(r"\s+", " ", value).strip()


class SmartTaskAnalyzer:
    """Classify a task and infer priority locally from keyword evidence."""

    @staticmethod
    def analyze_and_classify(task_description: str) -> dict:
        desc = _normalize(task_description)
        scores = {
            category: sum(1 for word in words if _normalize(word) in desc)
            for category, words in CATEGORY_KEYWORDS.items()
        }
        category = max(scores, key=scores.get) if scores and max(scores.values()) else "general"

        if any(_normalize(word) in desc for word in URGENCY_KEYWORDS):
            priority = "urgent"
        elif any(_normalize(word) in desc for word in HIGH_PRIORITY_KEYWORDS):
            priority = "high"
        else:
            priority = "normal"

        suggested_agent = AGENT_BY_CATEGORY[category]
        return {
            "category": category,
            "priority": priority,
            "suggested_agent": suggested_agent,
            "analysis_note": (
                f"تحليل محلي بالكلمات المفتاحية: الفئة '{category}'، "
                f"الأولوية '{priority}'، والوكيل المقترح '{suggested_agent}'."
            ),
        }
