"""Multidisciplinary request intake and supervised planning workspace."""
from __future__ import annotations

import streamlit as st

from core.auth_context import CurrentUser
from core.page_views import get_company, invalidate_task_caches
from core.request_planner import build_request_plan
from core.validator import ValidationError


st.title("مركز الطلبات متعددة التخصصات")
st.caption(
    "حوّل فكرتك أو مشكلتك إلى مجالات عمل ومخرجات وخطة أولية، ثم احفظها كمهمة "
    "مرتبطة بمشروع بعد مراجعتها."
)

with st.expander("المجالات التي يغطيها النظام", expanded=False):
    from core.capabilities import get_capability_catalog

    for item in get_capability_catalog():
        st.markdown(f"**{item['name_ar']}**")
        st.write(item["description"])
        st.caption("المخرجات الممكنة: " + "، ".join(item["deliverables"]))

with st.form("multidisciplinary_request_form"):
    brief = st.text_area(
        "اشرح ما تريد إنجازه أو المشكلة التي تريد حلها",
        height=170,
        max_chars=4000,
        placeholder=(
            "مثال: أريد دراسة جدوى وتصميماً أولياً لمنصة إلكترونية، "
            "مع تحليل المخاطر وخطة تطويرها."
        ),
    )
    analyze = st.form_submit_button("تحليل الطلب وتحديد المجالات", type="primary")

if analyze:
    try:
        initial = build_request_plan(brief)
        st.session_state["multidisciplinary_routing"] = initial["routing"]
        st.session_state["multidisciplinary_brief"] = brief.strip()
        st.session_state.pop("multidisciplinary_plan", None)
    except ValueError as exc:
        st.warning(str(exc))

routing = st.session_state.get("multidisciplinary_routing")
saved_brief = st.session_state.get("multidisciplinary_brief", "")
if routing:
    st.subheader("نتيجة تحليل الطلب")
    if routing["capabilities"]:
        for key in routing["capabilities"]:
            from core.capabilities import CAPABILITIES

            item = CAPABILITIES[key]
            with st.expander(item["name_ar"], expanded=True):
                st.write(item["description"])
                st.markdown("**المخرجات المقترحة**")
                for deliverable in item["deliverables"]:
                    st.markdown(f"- {deliverable}")
                st.warning(item["boundary"])
    else:
        st.info("لم يتم تحديد مجال متخصص. سيُحال الطلب إلى مراجعة عامة.")

    agent_labels = {
        "ceo": "المدير التنفيذي",
        "research": "الباحث",
        "consultant": "المستشار",
        "engineer": "المهندس",
        "marketing": "التسويق",
        "accountant": "المحاسب",
        "market_analyst": "محلل السوق",
    }
    recommended = routing["recommended_agents"]
    selected_agent = st.selectbox(
        "اختر الوكيل المسؤول عن إعداد الخطة الأولية",
        recommended,
        format_func=lambda key: agent_labels.get(key, key),
        key="multidisciplinary_selected_agent",
    )
    if st.button("إعداد خطة العمل", type="primary", key="build_multidisciplinary_plan"):
        try:
            st.session_state["multidisciplinary_plan"] = build_request_plan(
                saved_brief, selected_agent
            )
        except ValueError as exc:
            st.warning(str(exc))

plan = st.session_state.get("multidisciplinary_plan")
if plan:
    role_plan = plan["role_plan"]
    st.subheader(role_plan["title"])
    st.caption(f"{role_plan['agent']} · {plan['mode']}")
    st.markdown("**الخطوات المقترحة**")
    for step in role_plan["steps"]:
        st.markdown(f"- {step}")
    st.markdown("**أسئلة تحتاج إلى حسم**")
    for question in role_plan["questions"]:
        st.markdown(f"- {question}")
    st.warning(plan["notice"])
    st.info(
        "حفظ الطلب سينشئ مهمة مرتبطة بالمشروع المختار، ويسجل خطة الوكيل "
        "في مسار الموافقة البشرية. لن يبدأ أي تنفيذ خارجي."
    )

    company = get_company()
    projects = company.db.list_projects()
    project_options = {"بدون ربط بمشروع": None}
    project_options.update({
        f"#{item['id']} — {item['name']}": item["id"] for item in projects
    })
    selected_project_label = st.selectbox(
        "ربط الطلب بمشروع (اختياري)",
        list(project_options),
        key="multidisciplinary_project",
    )
    if st.button("حفظ الطلب كمهمة وإرسال الخطة للموافقة", type="primary"):
        task = None
        try:
            capability_names = "، ".join(
                item["name_ar"] for item in plan["capability_details"]
            ) or "مراجعة عامة"
            title_prefix = (
                plan["capability_details"][0]["name_ar"]
                if plan["capability_details"] else "طلب متعدد التخصصات"
            )
            task_title = f"{title_prefix}: {saved_brief[:120]}".strip()[:200]
            description = (
                f"وصف الطلب:\n{saved_brief}\n\n"
                f"المجالات المحددة: {capability_names}\n\n"
                f"الوكيل المقترح: {plan['selected_agent']}\n\n"
                "خطة العمل الأولية:\n"
                + "\n".join(f"- {step}" for step in role_plan["steps"])
                + "\n\nأسئلة مفتوحة:\n"
                + "\n".join(f"- {question}" for question in role_plan["questions"])
                + "\n\nتنبيه: خطة أولية محلية، وليست دليلاً على إنجاز المخرجات."
            )
            task = company.add_task_analyzed(
                {
                    "title": task_title,
                    "description": description[:4900],
                    "source": "multidisciplinary_request",
                    "category": "multidisciplinary",
                    "priority": "normal",
                    "price": 0,
                    "currency": company.settings.default_currency,
                    "project_id": project_options[selected_project_label],
                },
                user_name=CurrentUser.get_username(),
            )
            company.assign_role_agent(
                task["id"], plan["selected_agent"],
                user_name=CurrentUser.get_username(),
            )
            run = company.db.create_role_agent_run(
                task["id"], plan["selected_agent"], role_plan,
                requested_by=CurrentUser.get_username(),
            )
            invalidate_task_caches()
            st.success(
                f"تم حفظ المهمة #{task['id']} وإنشاء خطة الوكيل #{run['id']} "
                "بحالة انتظار الموافقة."
            )
            st.session_state.pop("multidisciplinary_plan", None)
        except (ValidationError, LookupError, ValueError) as exc:
            if task:
                st.error(
                    f"تم إنشاء المهمة #{task['id']}، لكن تعذر إكمال ربط الوكيل أو "
                    f"سجل الموافقة: {exc}. راجع صفحة المهام قبل إعادة المحاولة."
                )
            else:
                st.error(f"تعذر حفظ الطلب: {exc}")


# Optional model-assisted draft. No external action is performed from this workspace.
if routing:
    with st.expander("مسودة تحليل اختيارية عبر مزود LLM", expanded=False):
        st.caption(
            "الوضع الافتراضي محلي وبدون اتصال. إذا ضُبط AICOS_LLM_PROVIDER=openai "
            "وAICOS_LLM_API_KEY في بيئة التشغيل، سيُرسل وصف الطلب إلى OpenAI بعد "
            "ضغط الزر أدناه. لا تضع المفاتيح داخل المستودع."
        )
        if st.button("إنشاء مسودة تحليل", key="create_llm_draft"):
            try:
                from core.llm_provider import create_supervised_plan
                st.session_state["multidisciplinary_llm_draft"] = create_supervised_plan(
                    saved_brief
                )
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
        llm_draft = st.session_state.get("multidisciplinary_llm_draft")
        if llm_draft:
            st.caption(
                f"المزود: {llm_draft['provider']} · النموذج: {llm_draft['model']} "
                f"· الحالة: {llm_draft['mode']}"
            )
            st.subheader(llm_draft["summary"])
            for section, label in (
                ("deliverables", "المخرجات المقترحة"),
                ("assumptions", "الافتراضات"),
                ("risks", "المخاطر"),
                ("questions", "الأسئلة المفتوحة"),
            ):
                st.markdown(f"**{label}**")
                for item in llm_draft[section]:
                    st.markdown(f"- {item}")
            if llm_draft.get("fallback_reason"):
                st.warning(
                    "تعذر استخدام المزود الخارجي؛ تم الرجوع إلى التخطيط المحلي: "
                    + llm_draft["fallback_reason"]
                )
            st.warning(llm_draft["notice"])
            st.info(
                "المخرجات مسودة فقط وتتطلب مراجعة وموافقة بشرية. "
                "لا يتم تنفيذ أوامر أو تغييرات خارجية أو مالية."
            )
