"""Rule-based agents. They run offline and cost nothing; an AI model can be plugged in later.

Pipeline (each step is one agent):
    classifier : found       -> classified (sets the category) or rejected (blocked content)
    manager    : classified  -> assigned   (hands the task to the executor / human supervisor)
    accountant : done tasks  -> income entry in the ledger (only when asked, once per task)

The agents are deliberately simple keyword rules. They are a starting point, not a legal filter:
the human supervisor still decides what is accepted and executed.
"""
from __future__ import annotations

from .database import Database
from .logs import get_logger
from .smart_agent import SmartTaskAnalyzer

log = get_logger("agents")

CATEGORY_KEYWORDS = {
    "translation": ("ترجمة", "ترجم", "translate", "translation", "subtitle", "ترجمه"),
    "design": ("تصميم", "شعار", "logo", "design", "photoshop", "بانر", "banner", "هوية بصرية"),
    "programming": ("برمجة", "موقع", "تطبيق", "website", "code", "python", "script",
                    "app", "api", "wordpress", "ووردبريس", "برنامج"),
    "writing": ("كتابة", "مقال", "article", "content", "محتوى", "تدقيق", "تلخيص", "blog", "copywriting"),
    "marketing": ("تسويق", "إعلان", "اعلان", "seo", "marketing", "ads", "سوشيال", "social media"),
    "data": ("بيانات", "إكسل", "اكسل", "excel", "data", "تحليل", "spreadsheet", "csv"),
    "video": ("فيديو", "مونتاج", "video", "montage", "animation", "موشن"),
}

# Requests the company does not execute. These tasks are rejected for the supervisor to review.
BLOCKED_KEYWORDS = (
    "اختراق", "هاك", "hack", "crack", "كراك",
    "تقييمات وهمية", "fake review", "متابعين وهميين", "fake followers",
    "حل امتحان", "حل اختبار", "exam answers", "حل واجب جامعي", "بحث تخرج جاهز",
    "سبام", "spam", "تزوير", "forge",
)


def classify(title: str, description: str = "") -> str:
    """Return the best-matching category, or 'general' when nothing matches."""
    text = f"{title} {description}".lower()
    best, best_hits = "general", 0
    for category, words in CATEGORY_KEYWORDS.items():
        hits = sum(1 for w in words if w.lower() in text)
        if hits > best_hits:
            best, best_hits = category, hits
    return best


def blocked_reason(title: str, description: str = "") -> str | None:
    text = f"{title} {description}".lower()
    for word in BLOCKED_KEYWORDS:
        if word.lower() in text:
            return word
    return None


def run_classifier(db: Database) -> list[dict]:
    actions = []
    for task in reversed(db.list_tasks("found")):
        reason = blocked_reason(task["title"], task["description"])
        if reason:
            db.update_task(task["id"], status="rejected", agent="classifier")
            msg = f"رُفضت المهمة لاحتوائها على: {reason}"
        else:
            analysis = SmartTaskAnalyzer.analyze_and_classify(
                f"{task['title']} {task['description']}"
            )
            category = task["category"] or analysis["category"]
            current_priority = task.get("priority") or "normal"
            priority = (
                analysis["priority"]
                if analysis["priority"] in {"urgent", "high"}
                else current_priority
            )
            db.update_task(
                task["id"], status="classified", category=category,
                priority=priority, agent="classifier"
            )
            msg = (
                f"صُنّفت المهمة: {category}؛ الأولوية: {priority}؛ "
                f"الوكيل المقترح: {analysis['suggested_agent']}"
            )
        db.add_activity("classifier", msg, task["id"])
        actions.append({"agent": "classifier", "task_id": task["id"], "action": msg})
    return actions


def run_manager(db: Database) -> list[dict]:
    actions = []
    for task in reversed(db.list_tasks("classified")):
        db.update_task(task["id"], status="assigned", agent="executor")
        msg = "أُسندت المهمة إلى المنفِّذ بانتظار المشرف"
        db.add_activity("manager", msg, task["id"])
        actions.append({"agent": "manager", "task_id": task["id"], "action": msg})
    return actions


def run_accountant(db: Database) -> list[dict]:
    """Record income for completed tasks. Safe to run repeatedly: each task is recorded once."""
    actions = []
    for task in db.tasks_missing_income():
        db.add_ledger_entry({
            "task_id": task["id"], "kind": "income", "amount": task["price"],
            "currency": task["currency"], "note": "مسجّل تلقائياً: مهمة مكتملة",
        })
        msg = f"سُجّل دخل {task['price']:g} {task['currency']}"
        db.add_activity("accountant", msg, task["id"])
        actions.append({"agent": "accountant", "task_id": task["id"], "action": msg})
    return actions


def run_pipeline(db: Database) -> list[dict]:
    """Classifier then manager. The accountant is run separately, on purpose."""
    return run_classifier(db) + run_manager(db)
