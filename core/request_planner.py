"""Request planning helpers for multidisciplinary AICompanyOS work."""
from __future__ import annotations

from typing import Any

from core.ai_agents import AGENTS, run_agent
from core.capabilities import CAPABILITIES, route_request


def build_request_plan(brief: str, agent_key: str | None = None) -> dict[str, Any]:
    """Combine capability routing with one transparent role-agent work plan."""
    routing = route_request(brief)
    recommended = routing["recommended_agents"]
    selected = agent_key or recommended[0]
    if selected not in AGENTS:
        raise ValueError("الوكيل المختار غير معروف.")
    if selected not in recommended:
        raise ValueError("اختر وكيلاً من الوكلاء المقترحين لهذا الطلب.")

    details = [CAPABILITIES[key] for key in routing["capabilities"]]
    role_plan = run_agent(selected, brief)
    return {
        "routing": routing,
        "capability_details": [
            {
                "key": key,
                "name_ar": CAPABILITIES[key]["name_ar"],
                "description": CAPABILITIES[key]["description"],
                "deliverables": list(CAPABILITIES[key]["deliverables"]),
                "boundary": CAPABILITIES[key]["boundary"],
            }
            for key in routing["capabilities"]
        ],
        "recommended_agents": list(recommended),
        "selected_agent": selected,
        "role_plan": role_plan,
        "mode": "Rule-based / Offline",
        "notice": (
            "هذه خطة أولية مبنية على مطابقة الكلمات وقوالب الوكلاء المحلية. "
            "لم يتم إنتاج برنامج أو تصميم أو دراسة فعلية بمجرد إنشاء الخطة."
        ),
    }
