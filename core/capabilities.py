"""Deterministic capability catalog and request routing for AICompanyOS.

This module describes the multidisciplinary work the product is intended to
support. Routing is keyword-based and offline; it is not an LLM, live research,
professional certification, or autonomous execution engine.
"""
from __future__ import annotations

from typing import Any

CAPABILITIES: dict[str, dict[str, Any]] = {
    "software_engineering": {
        "name": "Software engineering",
        "name_ar": "هندسة وتطوير البرمجيات",
        "description": "تحليل المتطلبات وتصميم الأنظمة وقواعد البيانات والواجهات، والبرمجة والاختبار وتصحيح الأخطاء والتوثيق والصيانة.",
        "deliverables": ["وثيقة المتطلبات", "تصميم معماري وتقني", "كود المصدر", "اختبارات وتقاريرها", "توثيق التشغيل والصيانة"],
        "agents": ["engineer", "consultant", "research"],
        "keywords": ("برنامج", "برمجة", "تطبيق", "موقع", "منصة رقمية", "كود", "code", "software", "website", "web app", "api", "database", "قاعدة بيانات", "تصحيح الأخطاء", "اختبار برمجيات"),
        "boundary": "يلزم اختبار الكود ومراجعته أمنياً قبل النشر؛ لا يُفترض أن الخطة وحدها تعني أن البرنامج قد نُفّذ.",
    },
    "visual_design": {
        "name": "Visual and product design",
        "name_ar": "التصميم البصري وتصميم المنتجات",
        "description": "تصميم UI/UX والهوية البصرية والشعارات والمواد الإعلانية والنماذج الأولية للمنتجات.",
        "deliverables": ["موجز التصميم", "اتجاهات بصرية", "مخططات واجهات أولية", "مواصفات التصميم", "قائمة مراجعة قابلية الاستخدام"],
        "agents": ["engineer", "marketing", "consultant"],
        "keywords": ("تصميم", "شعار", "هوية بصرية", "واجهة", "واجهات", "ui", "ux", "تصميم تجربة المستخدم", "تصميم تطبيق", "تصميم موقع", "اعلان", "إعلان", "banner", "logo", "branding", "mockup", "prototype"),
        "boundary": "يجب تحديد المقاسات والصيغ وحقوق الأصول؛ التصور الأولي ليس ملف إنتاج نهائياً ما لم يُنشأ ويُراجع فعلياً.",
    },
    "architectural_concepts": {
        "name": "Architectural concepts",
        "name_ar": "التصورات والدراسات المعمارية",
        "description": "إعداد موجز معماري وتحليل احتياجات المساحات والوظائف والبرنامج المساحي والبدائل التصورية.",
        "deliverables": ["موجز المشروع", "برنامج وظيفي ومساحي مبدئي", "بدائل توزيع وتصوّر", "جدول افتراضات وقيود", "ملاحظات مراجعة"],
        "agents": ["engineer", "research", "consultant"],
        "keywords": ("عمارة", "معماري", "معمارية", "تصور معماري", "تصميم معماري", "مخطط معماري", "مبنى", "بناية", "فيلا", "شقة", "مساحة", "توزيع الغرف", "architectural", "architecture", "floor plan", "building design", "3d building"),
        "boundary": "المخرجات تصورية وغير صالحة وحدها للتنفيذ أو الترخيص؛ يجب أن يراجعها ويعتمدها مهندس/معماري مؤهل وفق القوانين المحلية.",
    },
    "feasibility_studies": {
        "name": "Feasibility and project development",
        "name_ar": "دراسات الجدوى وتطوير المشاريع",
        "description": "تحليل السوق والتكاليف والإيرادات والتدفقات النقدية ونقطة التعادل والسيناريوهات والمخاطر وخطة الإطلاق.",
        "deliverables": ["ملخص تنفيذي", "فرضيات السوق", "نموذج تكاليف وإيرادات", "تحليل نقطة التعادل", "سيناريوهات ومخاطر", "خارطة تنفيذ"],
        "agents": ["market_analyst", "accountant", "research", "consultant", "ceo"],
        "keywords": ("دراسة جدوى", "جدوى اقتصادية", "مشروع تجاري", "مشروع صناعي", "تكلفة المشروع", "تكاليف", "الإيرادات", "المداخيل", "نقطة التعادل", "ربحية", "استثمار", "business plan", "feasibility", "break even", "market size", "cash flow", "roi"),
        "boundary": "النتائج تعتمد على جودة البيانات والافتراضات؛ يجب تمييز الأرقام المؤكدة عن التقديرات وإجراء تحقق سوقي ومالي قبل الاستثمار.",
    },
    "research_problem_solving": {
        "name": "Research and problem solving",
        "name_ar": "البحث وحل المشكلات والابتكار",
        "description": "تحديد المشكلة وأسبابها، جمع الأدلة، مقارنة البدائل، تقييم المخاطر، واقتراح حلول قابلة للاختبار والتحسين.",
        "deliverables": ["تعريف المشكلة", "أسئلة وخطة بحث", "تحليل الأسباب", "مقارنة البدائل", "توصية مبررة", "خطة اختبار وتحسين"],
        "agents": ["research", "consultant", "market_analyst", "engineer"],
        "keywords": ("بحث", "حل مشكلة", "حلول", "اقتراحات", "اقتراح حل", "تحليل المشكلة", "سبب المشكلة", "تطوير المشروع", "تحسين", "ابتكار", "مخاطر محتملة", "بدائل", "research", "problem solving", "root cause", "improvement", "innovation", "risk analysis"),
        "boundary": "يجب إرفاق المصادر وتواريخها عند إجراء بحث فعلي؛ التوصيات غير المتحققة تبقى فرضيات وليست حقائق.",
    },
    "business_operations": {
        "name": "Business operations",
        "name_ar": "إدارة وتشغيل الشركة",
        "description": "إدارة العملاء والمشاريع والمهام والموارد والفواتير والعمليات المالية والتقارير.",
        "deliverables": ["سجل العملاء والمشاريع", "خطة المهام", "تقارير التقدم", "ملخص مالي تشغيلي", "سجل الموافقات والقرارات"],
        "agents": ["ceo", "consultant", "accountant", "marketing"],
        "keywords": ("إدارة الشركة", "تسيير الشركة", "عميل", "زبون", "مشروع", "مهمة", "فاتورة", "أداء", "دفعة", "ميزانية", "تقرير", "operations", "client", "invoice", "project management", "task management"),
        "boundary": "العمليات المالية والقانونية الحالية أساسية وليست بديلاً عن نظام محاسبي أو استشارة مهنية متخصصة.",
    },
}

def route_request(brief: str) -> dict[str, Any]:
    """Classify a request into one or more capability domains using keyword hits."""
    text = " ".join((brief or "").lower().split())
    if len(text) < 5:
        raise ValueError("أدخل وصفاً واضحاً للطلب (5 أحرف على الأقل).")

    scores: dict[str, int] = {}
    for key, capability in CAPABILITIES.items():
        hits = sum(1 for keyword in capability["keywords"] if keyword.lower() in text)
        if hits:
            scores[key] = hits

    ordered = sorted(scores, key=lambda key: (-scores[key], key))
    matched = ordered[:3]
    if not matched:
        return {
            "brief": brief.strip(),
            "primary_capability": "general_review",
            "capabilities": [],
            "recommended_agents": ["consultant", "research"],
            "scores": {},
            "mode": "Rule-based / Offline",
            "notice": "لم تتطابق الكلمات مع مجال محدد؛ يلزم توضيح الطلب ومراجعته بشرياً قبل توجيهه.",
        }

    agents: list[str] = []
    for key in matched:
        for agent in CAPABILITIES[key]["agents"]:
            if agent not in agents:
                agents.append(agent)

    return {
        "brief": brief.strip(),
        "primary_capability": matched[0],
        "capabilities": matched,
        "recommended_agents": agents,
        "scores": {key: scores[key] for key in matched},
        "mode": "Rule-based / Offline",
        "notice": "هذا توجيه أولي بالكلمات المفتاحية وليس تحليلاً من نموذج لغوي أو تنفيذاً فعلياً. راجع النطاق والمخرجات والقيود قبل الموافقة.",
    }


def get_capability_catalog() -> list[dict[str, Any]]:
    """Return a copy-safe public catalog without internal routing keywords."""
    return [
        {
            "key": key,
            "name": item["name"],
            "name_ar": item["name_ar"],
            "description": item["description"],
            "deliverables": list(item["deliverables"]),
            "agents": list(item["agents"]),
            "boundary": item["boundary"],
        }
        for key, item in CAPABILITIES.items()
    ]
