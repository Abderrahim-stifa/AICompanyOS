"""Supervised, domain-aware first drafts for project deliverables."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.deliverables import DOMAINS, _required_text
from core.llm_provider import Provider, create_supervised_plan


DOMAIN_GUIDANCE = {
    "software": "قدّم متطلبات وظيفية وغير وظيفية، حالات استخدام، معايير قبول، مخاطر تقنية وأسئلة مفتوحة. لا تدّع إنشاء كود إنتاجي.",
    "design": "قدّم موجز تصميم، المستخدمين المستهدفين، بنية المعلومات، مبادئ الهوية البصرية، مخرجات التصميم ومعايير التسليم. لا تدّع إنتاج ملفات تصميم نهائية.",
    "architecture": "قدّم تصوراً مفاهيمياً أولياً للبرنامج والمساحات والعلاقات والاعتبارات الوظيفية. لا تقدّم أبعاداً أو مخططات تنفيذية معتمدة ولا تدّع صلاحية البناء أو الترخيص.",
    "feasibility": "قدّم فرضيات السوق والعملاء والتكاليف والإيرادات والسيناريوهات والمخاطر والبيانات التي يجب التحقق منها. صنّف كل رقم تقديري كافتراض ولا تقدّمه كحقيقة.",
}


def generate_domain_draft(domain: str, brief: str, provider: Provider | None = None) -> dict[str, Any]:
    """Generate a bounded draft; it is never saved, approved, or executed here."""
    if domain not in DOMAINS:
        raise ValueError("مجال المخرج غير صالح.")
    brief = _required_text(brief, "وصف المطلوب", 3500)
    prompt = (
        f"المجال: {DOMAINS[domain]}\n"
        f"إرشادات المجال: {DOMAIN_GUIDANCE[domain]}\n"
        "أنتج مسودة أولية باللغة العربية. اجعل المخرجات والافتراضات والمخاطر "
        "والأسئلة واضحة ومحددة. لا تخترع مصادر أو نتائج بحث أو حقائق موثقة.\n"
        f"طلب المستخدم:\n{brief}"
    )
    result = create_supervised_plan(prompt, provider)
    assumptions = list(result["assumptions"])
    content_sections = [
        f"## الملخص\n{result['summary']}",
        "## المخرجات المقترحة\n" + "\n".join(f"- {item}" for item in result["deliverables"]),
        "## المخاطر\n" + "\n".join(f"- {item}" for item in result["risks"]),
        "## الأسئلة المفتوحة\n" + "\n".join(f"- {item}" for item in result["questions"]),
        "## حدود المسودة\nهذه مسودة مولّدة آلياً وغير متحقق منها. لا تمثل اعتماداً أو تنفيذاً فعلياً.",
    ]
    if domain == "architecture":
        content_sections.append(
            "> تنبيه مهني: تصور أولي فقط؛ ليس مخططاً تنفيذياً أو وثيقة ترخيص، "
            "ويحتاج مراجعة واعتماد معماري/مهندس مؤهل."
        )
    elif domain == "feasibility":
        content_sections.append(
            "> تنبيه مالي: التكاليف والإيرادات والتوقعات الواردة افتراضات تحتاج "
            "إلى بيانات سوقية ومحاسبية مستقلة للتحقق."
        )
    elif domain == "software":
        content_sections.append(
            "> تنبيه تقني: هذه مواصفات/خطة أولية وليست كوداً إنتاجياً أو اختباراً منفذاً."
        )
    else:
        content_sections.append(
            "> تنبيه تصميمي: هذه توجيهات وموجز تصميم وليست ملفات أصول نهائية جاهزة للإنتاج."
        )
    metadata = {
        "provider": result["provider"],
        "model": result["model"],
        "mode": result["mode"],
        "source": result["provenance"].get("source", "unknown"),
        "verification": "not_verified",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "requires_human_approval": True,
        "approved": False,
        "execution_performed": False,
    }
    for key in ("requested_provider", "fallback_reason"):
        if key in result:
            metadata[key] = result[key]
    return {
        "domain": domain,
        "title": result["summary"][:200],
        "content": "\n\n".join(content_sections)[:20000],
        "assumptions": assumptions,
        "risks": list(result["risks"]),
        "questions": list(result["questions"]),
        "deliverables": list(result["deliverables"]),
        "metadata": metadata,
    }
