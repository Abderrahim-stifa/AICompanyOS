"""Offline task analysis using transparent keyword heuristics.

This is deterministic rule-based classification, not a machine-learning model.
"""
from __future__ import annotations

import re
import unicodedata

from .text_match import has_word


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

# Pipeline agents coordinate processing; role agents own business-specialist work.
# Keep these mappings separate because tasks.agent and tasks.role_agent_key are
# different database fields with different responsibilities.
PIPELINE_AGENT_BY_CATEGORY = {
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

ROLE_AGENT_BY_CATEGORY = {
    "translation": "research",
    "programming": "engineer",
    "marketing": "marketing",
    "accounting": "accountant",
    "design": "engineer",
    "writing": "consultant",
    "data": "market_analyst",
    "video": "marketing",
    "general": "consultant",
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
            category: sum(1 for word in words if has_word(desc, _normalize(word)))
            for category, words in CATEGORY_KEYWORDS.items()
        }
        category = max(scores, key=scores.get) if scores and max(scores.values()) else "general"

        if any(has_word(desc, _normalize(word)) for word in URGENCY_KEYWORDS):
            priority = "urgent"
        elif any(has_word(desc, _normalize(word)) for word in HIGH_PRIORITY_KEYWORDS):
            priority = "high"
        else:
            priority = "normal"

        suggested_agent = PIPELINE_AGENT_BY_CATEGORY[category]
        suggested_role_agent = ROLE_AGENT_BY_CATEGORY[category]
        return {
            "category": category,
            "priority": priority,
            "suggested_agent": suggested_agent,
            "suggested_role_agent": suggested_role_agent,
            "analysis_note": (
                f"تحليل محلي بالكلمات المفتاحية: الفئة '{category}'، "
                f"الأولوية '{priority}'، وكيل Pipeline المقترح '{suggested_agent}'، "
                f"والوكيل المتخصص المقترح '{suggested_role_agent}'."
            ),
        }
