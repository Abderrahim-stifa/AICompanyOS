"""AICompanyOS — lightweight authenticated Streamlit multipage entrypoint."""
from __future__ import annotations

import streamlit as st

from core.auth import check_password, logout
from core.auth_context import CurrentUser
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

# 3. Streamlit-native page registry. Only these scripts are navigable;
# helper modules in pages/ remain internal imports.
navigation = st.navigation(
    [
        st.Page("pages/dashboard.py", title="لوحة التحكم", icon="📊", default=True),
        st.Page("pages/agents.py", title="الوكلاء", icon="🤖"),
        st.Page("pages/role_agents.py", title="الوكلاء السبعة", icon="🧠"),
        st.Page("pages/clients.py", title="العملاء", icon="👥"),
        st.Page("pages/projects.py", title="المشاريع", icon="📂"),
        st.Page("pages/tasks.py", title="المهام", icon="✅"),
        st.Page("pages/logs.py", title="سجل الأنشطة", icon="📜"),
        st.Page("pages/audit.py", title="سجل التعديلات", icon="🧾"),
        st.Page("pages/finance.py", title="الحسابات", icon="💰"),
        st.Page("pages/settings.py", title="الإعدادات", icon="⚙️"),
    ]
)

# 4. Shared sidebar controls; Streamlit renders native page navigation here.
with st.sidebar:
    st.markdown("### 🤖 AICompanyOS")
    st.markdown("---")
    st.write(f"👤 مرحباً، **{CurrentUser.get_username()}**")
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
