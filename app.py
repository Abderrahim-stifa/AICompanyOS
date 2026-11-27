"""AICompanyOS dashboard (Arabic, right-to-left).

Run:  python -m streamlit run app.py
"""
from __future__ import annotations

import html
import pandas as pd
import plotly.express as px
import streamlit as st

from core import agents as agents_mod
from core.auth_context import CurrentUser
from core.auth import check_password, logout
from core import backup as backup_mod
from core import ai_agents as role_agents
from core.agent_center import build_agent_overview
from core.init_db import list_role_agents, load_ui_settings, save_ui_settings
from core.service import Company
from core.ui_helpers import notify_and_refresh
from core.ui_theme import apply_custom_theme
from core.validator import CURRENCIES, PROJECT_STATUSES, TASK_STATUSES, ValidationError
from pages.logs_page import show_logs_page
from pages.audit_page import show_audit_page

st.set_page_config(page_title="AICompanyOS", page_icon="🤖", layout="wide")
APP_VERSION = "0.3.7"

TASK_AR = {
    "found": "تم العثور عليها", "classified": "مصنّفة", "assigned": "مُسندة",
    "in_progress": "قيد التنفيذ", "done": "مكتملة", "rejected": "مرفوضة",
}
PROJECT_AR = {"new": "جديد", "in_progress": "قيد التنفيذ", "done": "مكتمل", "on_hold": "متوقف"}
AGENT_AR = {
    "manager": "المدير", "finder": "الباحث عن المهام", "classifier": "المصنِّف",
    "executor": "المنفِّذ", "accountant": "المحاسب",
}
KIND_AR = {"income": "دخل", "expense": "مصروف"}

RTL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap');
:root { color-scheme: dark; }
html, body, .stApp, [data-testid="stSidebar"], [data-testid="stMarkdownContainer"],
.stTextInput, .stTextArea, .stSelectbox, .stNumberInput, .stRadio, .stAlert,
.stDateInput, .stMultiSelect, .stButton, .stDownloadButton {
 direction:rtl; text-align:right; font-family:'Cairo',sans-serif;
}
.stApp {background:radial-gradient(ellipse at 82% 0%,#202c68 0%,#111936 34%,#090f22 78%,#080d1b 100%);color:#eef3ff;}
[data-testid="stHeader"]{background:rgba(8,13,29,.94);}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#111a38 0%,#10182e 55%,#0c1428 100%);border-left:1px solid #29386d;}
[data-testid="stSidebar"] *{color:#eef3ff;}
[data-testid="stSidebar"] [data-testid="stRadio"] label{padding:9px 12px;border-radius:10px;margin:3px 0;transition:background .15s ease;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover{background:#26366a;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){background:linear-gradient(100deg,#5638d9,#315ee8);box-shadow:0 5px 18px #3325a855;}
.block-container{padding-top:1.25rem;padding-bottom:2.5rem;max-width:1540px;}
h1,h2,h3,p,label{ text-align:right;color:#f4f6ff;}
h1{font-weight:800;letter-spacing:-.4px;}
[data-testid="stMetric"]{background:linear-gradient(145deg,#1a2c58,#152344);border:1px solid #344b85;padding:17px;border-radius:17px;direction:rtl;text-align:right;box-shadow:0 8px 24px #03081744;}
[data-testid="stMetricLabel"]{color:#b9c8ee;}[data-testid="stMetricValue"]{color:#fff;font-weight:800;}
[data-testid="stDataFrame"],[data-testid="stTable"]{border:1px solid #34436d;border-radius:14px;overflow:hidden;}
.stButton button,.stDownloadButton button{border-radius:11px;border:1px solid #526bd0;background:linear-gradient(110deg,#4933c8,#245fe5);color:#fff;font-weight:700;min-height:2.55rem;}
.stButton button:hover,.stDownloadButton button:hover{border-color:#9a8bff;filter:brightness(1.12);color:#fff;}
.stTextInput input,.stTextArea textarea,.stNumberInput input,.stDateInput input,
.stSelectbox [data-baseweb="select"],.stMultiSelect [data-baseweb="select"]{
 background:#121e3c;color:#f4f6ff;border:1px solid #3a4e82;border-radius:10px;
}
[data-testid="stExpander"]{background:#142143;border:1px solid #344777;border-radius:13px;}
[data-testid="stAlert"]{border-radius:12px;}
hr{border-color:#34436d;}
.brand-header{display:flex;align-items:center;gap:16px;direction:ltr;margin:0 0 8px;padding:12px 18px;border:1px solid #344777;border-radius:18px;background:linear-gradient(110deg,#111b3cdd,#1c2250dd);box-shadow:0 12px 30px #03081755;}
.brand-name{font-family:'Cairo',sans-serif;font-weight:800;font-size:clamp(1.7rem,4vw,2.7rem);color:#f6f7ff;letter-spacing:-1px;}
.brand-tagline{color:#c1cafa;font-size:.95rem;margin-top:-4px;}
.brand-accent{height:3px;border-radius:4px;background:linear-gradient(90deg,#2478ff,#7c4dff,#16d49a);margin:10px 0 22px;}
.sidebar-brand{display:flex;align-items:center;gap:10px;padding:8px 4px 16px;border-bottom:1px solid #293960;margin-bottom:14px;}
.sidebar-brand-mark{width:42px;height:42px;border-radius:13px;display:grid;place-items:center;background:linear-gradient(135deg,#2384ff,#713ff0);font-size:24px;font-weight:800;color:white;}
.sidebar-brand-name{font-size:1.05rem;font-weight:800;direction:ltr;text-align:left;}
.sidebar-status{display:flex;align-items:center;gap:8px;color:#9eafd9;font-size:.82rem;margin-top:2px;}
.sidebar-status-dot{width:8px;height:8px;border-radius:50%;background:#19d995;box-shadow:0 0 10px #19d995;}
</style>
"""


@st.cache_resource
def get_company() -> Company:
    return Company()


def ar(mapping: dict, key: str) -> str:
    return mapping.get(key, key)


def table(rows: list[dict], columns: dict[str, str], maps: dict[str, dict] | None = None) -> None:
    """Show rows as a table with Arabic column names; `maps` translates coded values."""
    if not rows:
        st.info("لا توجد بيانات بعد.")
        return
    df = pd.DataFrame(rows)
    for col, mapping in (maps or {}).items():
        if col in df:
            df[col] = df[col].map(lambda v, m=mapping: ar(m, v))
    df = df[[c for c in columns if c in df]].rename(columns=columns)
    st.dataframe(df, width="stretch", hide_index=True)


def fail(exc: Exception) -> None:
    st.error(f"تعذّر الحفظ: {exc}")


# ----------------------------------------------------------------------------- pages

def page_dashboard(company: Company) -> None:
    st.header("لوحة التحكم")
    db = company.db
    clients, projects, tasks = db.list_clients(), db.list_projects(), db.list_tasks()
    summary = db.summary()

    role_overview = build_agent_overview(tasks)
    active_role_agents = sum(item["status"] == "active" for item in role_overview)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("👥 العملاء", len(clients))
    c2.metric("📂 المشاريع", len(projects))
    c3.metric("✅ المهام", len(tasks))
    c4.metric("🤖 وكلاء الأدوار", len(role_overview))
    c5.metric("🟢 وكلاء نشطون", active_role_agents)
    st.caption(f"AICompanyOS v{APP_VERSION}")

    st.subheader("🕒 آخر التعديلات")
    recent_logs = db.list_system_logs(limit=10)
    if recent_logs:
        recent_frame = pd.DataFrame(recent_logs)
        display_columns = [column for column in
                           ("id", "action", "entity_type", "entity_id", "user_name", "created_at")
                           if column in recent_frame.columns]
        st.dataframe(recent_frame[display_columns], width="stretch", hide_index=True)
    else:
        st.info("لا توجد تعديلات مسجلة بعد.")

    if summary["money"]:
        st.subheader("الحسابات")
        for row in summary["money"]:
            m1, m2, m3 = st.columns(3)
            m1.metric(f"الدخل ({row['currency']})", f"{row['income']:,.2f}")
            m2.metric(f"المصروفات ({row['currency']})", f"{row['expense']:,.2f}")
            m3.metric(f"الربح ({row['currency']})", f"{row['profit']:,.2f}")

    st.subheader("نشاط الوكلاء السبعة")
    agent_counts = pd.DataFrame([
        {"الوكيل": item["name_ar"], "عدد المهام": item["task_count"]}
        for item in role_overview
    ])
    agent_fig = px.bar(agent_counts, x="الوكيل", y="عدد المهام", title="المهام حسب الوكيل")
    st.plotly_chart(agent_fig, width="stretch")

    left, right = st.columns(2)
    with left:
        if projects:
            df = pd.DataFrame(projects)
            df["status"] = df["status"].map(lambda v: ar(PROJECT_AR, v))
            counts = df.groupby("status").size().reset_index(name="العدد")
            fig = px.pie(counts, names="status", values="العدد", title="حالة المشاريع")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("أضف مشاريع لتظهر الرسوم هنا.")
    with right:
        if tasks:
            df = pd.DataFrame(tasks)
            df["status"] = df["status"].map(lambda v: ar(TASK_AR, v))
            counts = df.groupby("status").size().reset_index(name="العدد")
            fig = px.bar(counts, x="status", y="العدد", title="حالة المهام",
                         labels={"status": "الحالة"})
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("أضف مهام لتظهر الرسوم هنا.")


def page_agents(company: Company) -> None:
    st.header("🤖 مركز الوكلاء")
    agents = company.db.list_agents()
    tasks = company.db.list_tasks()
    for agent in agents:
        mine = [t for t in tasks if t["agent"] == agent["name"]]
        active = sum(1 for t in mine if t["status"] in ("assigned", "in_progress"))
        st.success(f"{ar(AGENT_AR, agent['name'])} — {agent['specialty']} "
                   f"(مهام نشطة: {active}، الإجمالي: {len(mine)})")

    st.subheader("تشغيل الوكلاء")
    st.caption("المصنِّف يصنّف المهام الجديدة ويرفض المحظور منها، والمدير يسندها للمنفِّذ. "
               "المحاسب يسجّل دخلاً للمهام المكتملة مرة واحدة لكل مهمة، فشغّله بعد التأكد من استلام المبلغ.")
    col1, col2 = st.columns(2)
    results = None
    if col1.button("▶️ تشغيل المصنِّف والمدير"):
        results = agents_mod.run_pipeline(company.db)
    if col2.button("💰 تشغيل المحاسب"):
        results = agents_mod.run_accountant(company.db)
    if results is not None:
        if results:
            st.success(f"تم تنفيذ {len(results)} إجراء")
        else:
            st.info("لا يوجد شيء للتنفيذ الآن.")

    st.subheader("سجل النشاط")
    table(company.db.list_activity(),
          {"created_at": "الوقت", "agent": "الوكيل", "action": "الإجراء", "task_id": "رقم المهمة"},
          {"agent": AGENT_AR})



def page_role_agents(company: Company) -> None:
    st.header("مركز الوكلاء السبعة")
    st.caption("اختر دوراً واكتب المهمة للحصول على خطة عمل منظمة. النسخة الحالية محلية وقائمة على قواعد وقوالب، وليست نماذج LLM مستقلة.")
    st.subheader("الوكلاء السبعة")
    agent_cards = list_role_agents(company.settings.db_path)
    card_rows = st.columns(3)
    for index, agent in enumerate(agent_cards):
        with card_rows[index % 3]:
            last_activity = agent["last_activity"] or "لا يوجد نشاط مسجل"
            st.info(
                f"**{agent['name']}**\n\n"
                f"الدور: {agent['role']}\n\n"
                f"الحالة: {agent['status']}\n\n"
                f"عدد المهام: {agent['tasks_count']}\n\n"
                f"آخر نشاط: {last_activity}"
            )
    overview = build_agent_overview(company.db.list_tasks())
    active_count = sum(item["status"] == "active" for item in overview)
    ready_count = sum(item["status"] == "ready" for item in overview)
    m1, m2, m3 = st.columns(3)
    m1.metric("إجمالي الوكلاء", len(overview))
    m2.metric("وكلاء نشطون", active_count)
    m3.metric("وكلاء جاهزون", ready_count)
    st.dataframe(
        [{
            "الوكيل": item["name_ar"],
            "الحالة": {"active": "نشط", "ready": "جاهز", "disabled": "معطل"}[item["status"]],
            "إجمالي المهام": item["task_count"],
            "المهام النشطة": item["active_task_count"],
            "المهام المكتملة": item["completed_task_count"],
        } for item in overview],
        width="stretch", hide_index=True,
    )
    labels = {key: value["name_ar"] for key, value in role_agents.AGENTS.items()}
    selected = st.selectbox("الوكيل", list(labels), format_func=lambda key: labels[key])
    st.info(role_agents.AGENTS[selected]["purpose"])
    brief = st.text_area("وصف المهمة أو المشروع", height=150,
                         placeholder="مثال: نريد إطلاق متجر إلكتروني لبيع المنتجات المحلية...")
    if st.button("تشغيل الوكيل", type="primary", key="run_role_agent"):
        try:
            result = role_agents.run_agent(selected, brief)
            st.session_state["role_agent_result"] = result
            company.db.add_activity(selected, f"تم إعداد خطة أولية: {result['title']}")
        except ValueError as exc:
            st.warning(str(exc))

    result = st.session_state.get("role_agent_result")
    if result:
        st.subheader(result["title"])
        st.caption(f"{result['agent']} · {result['mode']}")
        st.markdown("**المهمة:** " + result["brief"])
        st.markdown("**خطوات العمل المقترحة**")
        for step in result["steps"]:
            st.markdown(f"- {step}")
        st.markdown("**أسئلة يجب حسمها**")
        for question in result["questions"]:
            st.markdown(f"- {question}")
        st.markdown("**ضوابط مشتركة**")
        for item in result["common"]:
            st.markdown(f"- {item}")
        st.warning(result["notice"])


def page_clients(company: Company) -> None:
    st.header("👥 العملاء")
    table(company.db.list_clients(),
          {"id": "الرقم", "name": "الاسم", "email": "البريد", "phone": "الهاتف", "created_at": "تاريخ الإضافة"})

    with st.form("add_client", clear_on_submit=True):
        st.subheader("إضافة عميل")
        name = st.text_input("الاسم")
        email = st.text_input("البريد الإلكتروني (اختياري)")
        phone = st.text_input("الهاتف (اختياري)")
        if st.form_submit_button("حفظ"):
            try:
                company.add_client({"name": name, "email": email, "phone": phone})
                st.success("تمت إضافة العميل")
                st.rerun()
            except ValidationError as exc:
                fail(exc)

    clients = company.db.list_clients()
    if clients:
        with st.expander("تعديل عميل"):
            options = {f"{c['id']} — {c['name']}": c for c in clients}
            choice = st.selectbox("اختر العميل", list(options), key="edit_client")
            current = options[choice]
            cid = current["id"]
            new_name = st.text_input("الاسم", value=current["name"], key=f"ec_name_{cid}")
            new_email = st.text_input("البريد الإلكتروني (اختياري)", value=current["email"], key=f"ec_email_{cid}")
            new_phone = st.text_input("الهاتف (اختياري)", value=current["phone"], key=f"ec_phone_{cid}")
            if st.button("حفظ التعديل", key="edit_client_btn"):
                try:
                    company.update_client(cid, {"name": new_name, "email": new_email, "phone": new_phone})
                    st.success("تم تعديل العميل")
                    st.rerun()
                except (ValidationError, LookupError) as exc:
                    fail(exc)

        with st.expander("حذف عميل"):
            options = {f"{c['id']} — {c['name']}": c["id"] for c in clients}
            choice = st.selectbox("اختر العميل", list(options), key="del_client")
            sure = st.checkbox("أؤكد الحذف", key="del_client_ok")
            if st.button("حذف", key="del_client_btn") and sure:
                company.delete_client(options[choice])
                st.rerun()


def page_projects(company: Company) -> None:
    st.header("📂 المشاريع")
    table(company.db.list_projects(),
          {"id": "الرقم", "name": "المشروع", "client_name": "العميل", "status": "الحالة",
           "budget": "الميزانية", "currency": "العملة"},
          {"status": PROJECT_AR})

    clients = company.db.list_clients()
    client_options = {"— بدون عميل —": None, **{f"{c['id']} — {c['name']}": c["id"] for c in clients}}
    with st.form("add_project", clear_on_submit=True):
        st.subheader("إضافة مشروع")
        name = st.text_input("اسم المشروع")
        client = st.selectbox("العميل", list(client_options))
        status = st.selectbox("الحالة", PROJECT_STATUSES, format_func=lambda v: ar(PROJECT_AR, v))
        budget = st.number_input("الميزانية", min_value=0.0, step=10.0)
        currency = st.selectbox("العملة", CURRENCIES, index=CURRENCIES.index(company.settings.default_currency)
                                if company.settings.default_currency in CURRENCIES else 0)
        if st.form_submit_button("حفظ"):
            try:
                company.add_project({"name": name, "client_id": client_options[client],
                                     "status": status, "budget": budget, "currency": currency})
                st.success("تمت إضافة المشروع")
                st.rerun()
            except (ValidationError, LookupError) as exc:
                fail(exc)

    projects = company.db.list_projects()
    if projects:
        with st.expander("تعديل مشروع"):
            options = {f"{p['id']} — {p['name']}": p for p in projects}
            choice = st.selectbox("اختر المشروع", list(options), key="full_edit_project")
            current = options[choice]
            pid = current["id"]
            new_name = st.text_input("اسم المشروع", value=current["name"], key=f"ep_name_{pid}")
            client_keys = list(client_options)
            current_client = next((k for k, v in client_options.items() if v == current["client_id"]),
                                  client_keys[0])
            new_client = st.selectbox("العميل", client_keys, index=client_keys.index(current_client),
                                      key=f"ep_client_{pid}")
            new_status = st.selectbox("الحالة", PROJECT_STATUSES, index=PROJECT_STATUSES.index(current["status"]),
                                      format_func=lambda v: ar(PROJECT_AR, v), key=f"ep_status_{pid}")
            new_budget = st.number_input("الميزانية", min_value=0.0, step=10.0,
                                         value=float(current["budget"]), key=f"ep_budget_{pid}")
            if st.button("حفظ تعديل المشروع", key="full_edit_project_btn"):
                try:
                    company.update_project(pid, {
                        "name": new_name, "client_id": client_options[new_client], "status": new_status,
                        "budget": new_budget, "currency": current["currency"],
                    })
                    st.success("تم تعديل المشروع")
                    st.rerun()
                except (ValidationError, LookupError) as exc:
                    fail(exc)

        with st.expander("تغيير حالة أو حذف مشروع"):
            options = {f"{p['id']} — {p['name']}": p["id"] for p in projects}
            choice = st.selectbox("اختر المشروع", list(options), key="edit_project")
            new_status = st.selectbox("الحالة الجديدة", PROJECT_STATUSES,
                                      format_func=lambda v: ar(PROJECT_AR, v), key="edit_project_status")
            col1, col2 = st.columns(2)
            if col1.button("تحديث الحالة"):
                company.set_project_status(options[choice], new_status)
                st.rerun()
            sure = col2.checkbox("أؤكد الحذف", key="del_project_ok")
            if col2.button("حذف المشروع") and sure:
                company.delete_project(options[choice])
                st.rerun()


@st.dialog("تأكيد الحذف")
def confirm_delete_dialog(company: Company, task_id: int, user_name: str) -> None:
    st.warning("سيتم حذف المهمة نهائياً. لا يمكن التراجع عن هذه العملية.")
    col_confirm, col_cancel = st.columns(2)
    with col_confirm:
        if st.button("نعم، احذف المهمة", type="primary", key="confirm_task_delete"):
            try:
                company.delete_task(task_id, user_name=user_name)
                notify_and_refresh("تم حذف المهمة وتسجيل العملية.")
            except (LookupError, ValueError) as exc:
                fail(exc)
    with col_cancel:
        if st.button("إلغاء", key="cancel_task_delete"):
            st.rerun()


def page_tasks(company: Company) -> None:
    st.header("✅ إدارة المهام")
    user_name = st.text_input(
        "المستخدم الحالي",
        value=CurrentUser.get_username(),
        max_chars=100,
        key="audit_user_input",
        disabled=True,
        help="هوية المستخدم الذي سجل الدخول، وتُستخدم في سجل التدقيق.",
    ).strip() or "system"
    CurrentUser.set_username(user_name)
    user_name = CurrentUser.get_username()

    tasks = company.db.list_tasks()
    agents = company.db.list_agents()
    role_agents = company.db.list_role_agents()
    pipeline_names = [item["name"] for item in agents]
    role_labels = {"— بدون إسناد —": None, **{
        f"{item['name']} — {item['role']}": item["agent_key"] for item in role_agents
    }}

    st.subheader("جميع المهام")
    status_filter = st.selectbox(
        "تصفية حسب الحالة", ["الكل", *TASK_STATUSES],
        format_func=lambda value: value if value == "الكل" else ar(TASK_AR, value),
        key="tasks_status_filter",
    )
    visible_tasks = [item for item in tasks if status_filter == "الكل" or item["status"] == status_filter]
    table(visible_tasks, {
        "id": "الرقم", "title": "المهمة", "description": "الوصف",
        "priority": "الأولوية", "status": "الحالة", "agent": "وكيل Pipeline",
        "role_agent_key": "وكيل الدور", "created_at": "تاريخ الإنشاء",
    }, {"status": TASK_AR, "agent": AGENT_AR})

    tab_create, tab_update, tab_delete = st.tabs(["إضافة مهمة", "تعديل / إسناد", "حذف مهمة"])
    with tab_create:
        with st.form("task_create_form", clear_on_submit=True):
            title = st.text_input("عنوان المهمة", max_chars=200)
            description = st.text_area("الوصف", max_chars=5000)
            source = st.text_input("المصدر")
            category = st.text_input("التصنيف")
            price = st.number_input("القيمة", min_value=0.0, step=1.0)
            priority = st.selectbox("الأولوية", ["low", "normal", "high", "urgent"], index=1)
            pipeline_agent = st.selectbox("وكيل Pipeline", ["— بدون إسناد —", *pipeline_names])
            if st.form_submit_button("إنشاء المهمة"):
                try:
                    created = company.add_task({
                        "title": title, "description": description, "source": source,
                        "category": category, "price": price,
                        "currency": company.settings.default_currency,
                        "priority": priority,
                    }, user_name=user_name)
                    if pipeline_agent != "— بدون إسناد —":
                        company.update_task(created["id"], {
                            "agent": pipeline_agent, "user_name": user_name,
                        })
                    notify_and_refresh(f"تم إنشاء المهمة رقم {created['id']}")
                except (ValidationError, LookupError, ValueError) as exc:
                    fail(exc)

    with tab_update:
        if not tasks:
            st.info("لا توجد مهام لتعديلها.")
        else:
            task_options = {f"#{item['id']} — {item['title']}": item["id"] for item in tasks}
            selected_label = st.selectbox("اختر المهمة", list(task_options), key="task_edit_choice")
            selected = next(item for item in tasks if item["id"] == task_options[selected_label])
            with st.form("task_update_form"):
                edit_title = st.text_input("العنوان", value=selected["title"], max_chars=200)
                edit_description = st.text_area("الوصف", value=selected["description"], max_chars=5000)
                edit_source = st.text_input("المصدر", value=selected["source"])
                edit_category = st.text_input("التصنيف", value=selected["category"])
                edit_price = st.number_input("القيمة", min_value=0.0, value=float(selected["price"]), step=1.0)
                priorities = ["low", "normal", "high", "urgent"]
                edit_priority = st.selectbox("الأولوية", priorities,
                    index=priorities.index(selected.get("priority", "normal")))
                edit_status = st.selectbox("الحالة", TASK_STATUSES,
                    index=TASK_STATUSES.index(selected["status"]),
                    format_func=lambda value: ar(TASK_AR, value))
                current_pipeline = selected.get("agent") or "— بدون إسناد —"
                pipeline_index = (["— بدون إسناد —", *pipeline_names].index(current_pipeline)
                                  if current_pipeline in ["— بدون إسناد —", *pipeline_names] else 0)
                edit_pipeline = st.selectbox("وكيل Pipeline", ["— بدون إسناد —", *pipeline_names],
                                             index=pipeline_index)
                current_role = next((label for label, key in role_labels.items()
                                     if key == selected.get("role_agent_key")), "— بدون إسناد —")
                edit_role = st.selectbox("وكيل الدور", list(role_labels),
                                         index=list(role_labels).index(current_role))
                if st.form_submit_button("حفظ التعديلات"):
                    try:
                        company.update_task(selected["id"], {
                            "title": edit_title, "description": edit_description,
                            "source": edit_source, "category": edit_category,
                            "price": edit_price, "currency": company.settings.default_currency,
                            "priority": edit_priority, "status": edit_status,
                            "agent": "" if edit_pipeline == "— بدون إسناد —" else edit_pipeline,
                            "user_name": user_name,
                        })
                        role_key = role_labels[edit_role]
                        if role_key and role_key != selected.get("role_agent_key"):
                            company.assign_role_agent(selected["id"], role_key, user_name=user_name)
                        elif not role_key and selected.get("role_agent_key"):
                            company.unassign_role_agent(selected["id"], user_name=user_name)
                        notify_and_refresh("تم تحديث المهمة.")
                    except (ValidationError, LookupError, ValueError) as exc:
                        fail(exc)

    with tab_delete:
        if not tasks:
            st.info("لا توجد مهام لحذفها.")
        else:
            delete_options = {f"#{item['id']} — {item['title']}": item["id"] for item in tasks}
            delete_label = st.selectbox("المهمة المراد حذفها", list(delete_options), key="task_delete_choice")
            if st.button("حذف المهمة", type="primary", key="open_task_delete_dialog"):
                confirm_delete_dialog(company, delete_options[delete_label], user_name)

    st.caption("كل عمليات الإنشاء والتعديل والحذف تسجل المستخدم والكيان ورقم المهمة في سجل الأنشطة.")

def page_finance(company: Company) -> None:
    st.header("💰 الحسابات")
    for row in company.db.summary()["money"]:
        a, b, c = st.columns(3)
        a.metric(f"الدخل ({row['currency']})", f"{row['income']:,.2f}")
        b.metric(f"المصروفات ({row['currency']})", f"{row['expense']:,.2f}")
        c.metric(f"الربح ({row['currency']})", f"{row['profit']:,.2f}")

    table(company.db.list_ledger(),
          {"id": "الرقم", "kind": "النوع", "amount": "المبلغ", "currency": "العملة",
           "task_id": "رقم المهمة", "note": "ملاحظة", "created_at": "التاريخ"},
          {"kind": KIND_AR})

    tasks = company.db.list_tasks()
    task_options = {"— بدون مهمة —": None, **{f"{t['id']} — {t['title']}": t["id"] for t in tasks}}
    with st.form("add_ledger", clear_on_submit=True):
        st.subheader("تسجيل عملية")
        kind = st.selectbox("النوع", list(KIND_AR), format_func=lambda v: KIND_AR[v])
        amount = st.number_input("المبلغ", min_value=0.0, step=1.0)
        currency = st.selectbox("العملة", CURRENCIES, index=CURRENCIES.index(company.settings.default_currency)
                                if company.settings.default_currency in CURRENCIES else 0)
        task = st.selectbox("المهمة المرتبطة", list(task_options))
        note = st.text_input("ملاحظة (اختياري)")
        if st.form_submit_button("حفظ"):
            try:
                company.add_ledger({"kind": kind, "amount": amount, "currency": currency,
                                    "task_id": task_options[task], "note": note})
                st.success("تم تسجيل العملية")
                st.rerun()
            except (ValidationError, LookupError) as exc:
                fail(exc)


def page_settings(company: Company) -> None:
    st.header("⚙️ الإعدادات والنسخ الاحتياطي")
    s = company.settings
    preferences = load_ui_settings(s.db_path)

    st.subheader("إعدادات الشركة والواجهة")
    with st.form("ui_preferences"):
        company_name = st.text_input("اسم الشركة", value=preferences["company_name"], max_chars=100)
        language = st.selectbox(
            "لغة التفضيل",
            ["ar", "en"],
            index=["ar", "en"].index(preferences["language"] if preferences["language"] in {"ar", "en"} else "ar"),
            format_func=lambda value: "العربية" if value == "ar" else "English",
            help="حالياً محتوى الواجهة بالعربية؛ اختيار English يُحفظ كتفضيل تمهيداً لإضافة الترجمة.",
        )
        dark_mode = st.toggle("الوضع الليلي", value=preferences["dark_mode"])
        if st.form_submit_button("حفظ الإعدادات"):
            try:
                save_ui_settings({
                    "company_name": company_name,
                    "language": language,
                    "dark_mode": dark_mode,
                    "theme": preferences["theme"],
                }, s.db_path)
                st.success("تم حفظ الإعدادات. أعد تحميل الصفحة لتطبيق المظهر.")
                st.rerun()
            except (TypeError, ValueError) as exc:
                fail(exc)

    st.subheader("النسخ الاحتياطي")
    if st.button("إنشاء نسخة احتياطية الآن"):
        path = backup_mod.create_backup(s.db_path, s.backup_dir, s.backup_keep)
        st.success(f"تم الحفظ: {path.name}")
    backups = backup_mod.list_backups(s.backup_dir)
    if backups:
        st.caption(f"عدد النسخ المحفوظة: {len(backups)} — آخرها: {backups[-1].name}")

    st.subheader("بيانات تجريبية")
    st.caption("تضيف 3 عملاء و3 مشاريع و3 مهام للتجربة، ولا تعمل إذا كان لديك عملاء مسبقاً.")
    if st.button("إدخال بيانات تجريبية"):
        if company.db.seed_demo():
            st.success("تمت إضافة البيانات التجريبية")
            st.rerun()
        else:
            st.warning("لديك عملاء مسبقاً، لم يتم إدخال شيء.")

    st.subheader("المسارات")
    st.code(f"قاعدة البيانات: {s.db_path}\nالسجلات: {s.log_dir}\nالنسخ الاحتياطية: {s.backup_dir}")


PAGES = {
    "لوحة التحكم": page_dashboard,
    "الوكلاء": page_agents,
    "الوكلاء السبعة": page_role_agents,
    "العملاء": page_clients,
    "المشاريع": page_projects,
    "المهام": page_tasks,
    "سجل الأنشطة": show_logs_page,
    "سجل التعديلات": show_audit_page,
    "الحسابات": page_finance,
    "الإعدادات": page_settings,
}


def main() -> None:
    apply_custom_theme()
    if not check_password():
        return

    authenticated_username = st.session_state.get("username", "")
    if authenticated_username:
        CurrentUser.set_username(authenticated_username)

    company = get_company()
    preferences = load_ui_settings(company.settings.db_path)
    st.markdown(RTL_CSS, unsafe_allow_html=True)
    if not preferences["dark_mode"]:
        st.markdown("""
        <style>
        :root {color-scheme:light !important;}
        .stApp {background:#f4f6fb !important;color:#172033 !important;}
        h1,h2,h3,p,label,[data-testid="stMarkdownContainer"] {color:#172033 !important;}
        [data-testid="stSidebar"] {background:#e8edf6 !important;}
        [data-testid="stSidebar"] * {color:#172033 !important;}
        [data-testid="stMetric"] {background:#fff !important;border-color:#d8deea !important;}
        [data-testid="stMetricLabel"],[data-testid="stMetricValue"] {color:#172033 !important;}
        .stTextInput input,.stTextArea textarea,.stSelectbox [data-baseweb="select"] {background:#fff !important;color:#172033 !important;}
        </style>
        """, unsafe_allow_html=True)
    st.markdown("""
    <div class="brand-header">
      <svg width="76" height="76" viewBox="0 0 120 120" role="img" aria-label="AICompanyOS robot logo">
        <defs><linearGradient id="shell" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#f4d9ff"/><stop offset="1" stop-color="#a88bd0"/></linearGradient><linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff06a"/><stop offset="1" stop-color="#ffad22"/></linearGradient></defs>
        <path d="M22 38Q22 20 42 20H78Q98 20 98 40V82Q98 101 78 101H42Q22 101 22 82Z" fill="url(#shell)" stroke="#ff4d86" stroke-width="3"/>
        <rect x="31" y="39" width="58" height="31" rx="14" fill="#242044"/><ellipse cx="44" cy="54" rx="5" ry="9" fill="#35c7ff"/><ellipse cx="76" cy="54" rx="5" ry="9" fill="#35c7ff"/><rect x="45" y="80" width="30" height="9" rx="4.5" fill="#33254c"/><rect x="43" y="8" width="34" height="11" rx="5.5" fill="url(#gold)"/><path d="M18 42V76M102 42V76" stroke="#ff4d86" stroke-width="6" stroke-linecap="round"/><circle cx="17" cy="33" r="6" fill="#ff4d86"/><circle cx="103" cy="33" r="6" fill="#ff4d86"/>
      </svg>
      <div><div class="brand-name">{__COMPANY_NAME__}</div><div class="brand-tagline">AI Business Operating System · v{APP_VERSION}</div></div>
    </div><div class="brand-accent"></div>
    """.replace("{__COMPANY_NAME__}", html.escape(preferences["company_name"])).replace("{APP_VERSION}", APP_VERSION), unsafe_allow_html=True)
    st.sidebar.markdown("""
    <div class="sidebar-brand">
      <div class="sidebar-brand-mark">A</div>
      <div><div class="sidebar-brand-name">AICompanyOS</div>
      <div class="sidebar-status"><span class="sidebar-status-dot"></span> النظام جاهز للعمل</div></div>
    </div>
    """, unsafe_allow_html=True)
    page = st.sidebar.radio("مساحة العمل", list(PAGES), label_visibility="collapsed")
    st.sidebar.caption(f"مسجل الدخول: {CurrentUser.get_username()}")
    if st.sidebar.button("تسجيل الخروج", use_container_width=True):
        logout()
        st.rerun()
    st.sidebar.markdown(
        f'<div style="margin-top:24px;padding:12px;border:1px solid #293960;border-radius:12px;'
        f'background:#172342;color:#b9c8ee;font-size:.8rem;text-align:center">AICompanyOS · v{APP_VERSION}</div>',
        unsafe_allow_html=True,
    )
    PAGES[page](company)


main()
