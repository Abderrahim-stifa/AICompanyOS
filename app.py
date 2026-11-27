"""AICompanyOS — lightweight authenticated Streamlit multipage entrypoint."""
from __future__ import annotations

import streamlit as st

from core import backup as backup_mod
from core.auth import check_password, logout
from core.auth_context import CurrentUser
from core.page_views import get_company, get_dashboard_data, invalidate_task_caches
from core.smart_agent import SmartTaskAnalyzer
from core.ui_helpers import notify_and_refresh
from core.validator import ValidationError
from core.ui_theme import apply_custom_theme


st.set_page_config(
    page_title="AICompanyOS",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 1. Shared theme and authentication gate.
apply_custom_theme()
if not check_password():
    st.stop()

# 2. Bind the authenticated identity to the audit context.
CurrentUser.set_username(st.session_state.get("username", "system"))

# 2a. Create a daily database backup after authentication, at most once per 24h.
company = get_company()
backup_mod.auto_backup_if_needed(company.settings.db_path, company.settings.backup_dir)

# 3. Streamlit-native page registry. Only these scripts are navigable;
# helper modules in pages/ remain internal imports.
navigation = st.navigation(
    [
        st.Page("pages/dashboard.py", title="لوحة التحكم", icon="📊", default=True),
        st.Page("pages/agents.py", title="الوكلاء", icon="🤖"),
        st.Page("pages/role_agents.py", title="الوكلاء السبعة", icon="🧠"),
        st.Page("pages/agent_runs.py", title="موافقات تشغيل الوكلاء", icon="🧾"),
        st.Page("pages/clients.py", title="العملاء", icon="👥"),
        st.Page("pages/projects.py", title="المشاريع", icon="📂"),
        st.Page("pages/tasks.py", title="المهام", icon="✅"),
        st.Page("pages/logs.py", title="سجل الأنشطة", icon="📜"),
        st.Page("pages/audit.py", title="سجل التعديلات", icon="🧾"),
        st.Page("pages/finance.py", title="الحسابات", icon="💰"),
        st.Page("pages/settings.py", title="الإعدادات", icon="⚙️"),
    ]
)


@st.dialog("⚡ إجراء سريع")
def quick_action_dialog() -> None:
    """Create a task or client from any page without changing navigation."""
    company = get_company()
    action = st.radio(
        "نوع الإجراء",
        ["إضافة مهمة", "إضافة عميل"],
        horizontal=True,
        key="quick_action_type",
    )

    if action == "إضافة مهمة":
        with st.form("quick_add_task_form", clear_on_submit=True):
            title = st.text_input("عنوان المهمة", max_chars=200)
            description = st.text_area("الوصف", max_chars=5000)
            price = st.number_input("القيمة", min_value=0.0, step=1.0)
            submitted = st.form_submit_button("🧠 تحليل وحفظ المهمة", type="primary")
        if submitted:
            try:
                if not title.strip():
                    st.error("أدخل عنوان المهمة.")
                    return
                analysis = SmartTaskAnalyzer.analyze_and_classify(
                    f"{title} {description}"
                )
                company.add_task(
                    {
                        "title": title,
                        "description": description,
                        "source": "quick_action",
                        "category": analysis["category"],
                        "price": price,
                        "currency": company.settings.default_currency,
                        "priority": analysis["priority"],
                    },
                    user_name=CurrentUser.get_username(),
                )
                invalidate_task_caches()
                notify_and_refresh(
                    f"تم إنشاء المهمة. الفئة: {analysis['category']}، "
                    f"الأولوية: {analysis['priority']}."
                )
            except (ValidationError, LookupError, ValueError) as exc:
                st.error(str(exc))
    else:
        with st.form("quick_add_client_form", clear_on_submit=True):
            name = st.text_input("اسم العميل", max_chars=150)
            email = st.text_input("البريد الإلكتروني (اختياري)")
            phone = st.text_input("الهاتف (اختياري)", max_chars=30)
            submitted = st.form_submit_button("حفظ العميل", type="primary")
        if submitted:
            try:
                company.add_client(
                    {"name": name, "email": email, "phone": phone}
                )
                get_dashboard_data.clear()
                notify_and_refresh("تمت إضافة العميل بنجاح.")
            except (ValidationError, LookupError, ValueError) as exc:
                st.error(str(exc))

# 4. Shared sidebar controls; Streamlit renders native page navigation here.
with st.sidebar:
    st.markdown("### 🤖 AICompanyOS")
    st.markdown("---")
    st.write(f"👤 مرحباً، **{CurrentUser.get_username()}**")
    st.markdown("---")
    if st.button("⚡ إجراء سريع", use_container_width=True, type="primary"):
        quick_action_dialog()
    st.markdown("---")
    if st.button("🚪 تسجيل الخروج", use_container_width=True):
        logout()
        st.rerun()
    st.markdown(
        "<div style='text-align:center; margin-top:50px; color:#64748b; "
        "font-size:12px'>v0.5.0 Ultra-Fast</div>",
        unsafe_allow_html=True,
    )

navigation.run()
