"""AICompanyOS dashboard (Arabic, right-to-left).

Run:  python -m streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from core import backup as backup_mod
from core.service import Company
from core.validator import CURRENCIES, PROJECT_STATUSES, TASK_STATUSES, ValidationError

st.set_page_config(page_title="AICompanyOS", page_icon="🤖", layout="wide")

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
html, body, .stApp, [data-testid="stSidebar"], [data-testid="stMarkdownContainer"],
.stTextInput, .stTextArea, .stSelectbox, .stNumberInput, .stRadio, .stAlert {
    direction: rtl;
    text-align: right;
}
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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 العملاء", len(clients))
    c2.metric("📂 المشاريع", len(projects))
    c3.metric("✅ المهام", len(tasks))
    c4.metric("🤖 الوكلاء", len(db.list_agents()))

    if summary["money"]:
        st.subheader("الحسابات")
        for row in summary["money"]:
            m1, m2, m3 = st.columns(3)
            m1.metric(f"الدخل ({row['currency']})", f"{row['income']:,.2f}")
            m2.metric(f"المصروفات ({row['currency']})", f"{row['expense']:,.2f}")
            m3.metric(f"الربح ({row['currency']})", f"{row['profit']:,.2f}")

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
    client_options = {"— بدون عميل —": None, **{c["name"]: c["id"] for c in clients}}
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


def page_tasks(company: Company) -> None:
    st.header("✅ المهام")
    status_filter = st.selectbox("تصفية حسب الحالة", ["الكل", *TASK_STATUSES],
                                 format_func=lambda v: v if v == "الكل" else ar(TASK_AR, v))
    table(company.db.list_tasks(None if status_filter == "الكل" else status_filter),
          {"id": "الرقم", "title": "المهمة", "source": "المصدر", "category": "التصنيف",
           "price": "السعر", "currency": "العملة", "status": "الحالة", "agent": "الوكيل"},
          {"status": TASK_AR, "agent": AGENT_AR})

    with st.form("add_task", clear_on_submit=True):
        st.subheader("إضافة مهمة")
        title = st.text_input("عنوان المهمة")
        description = st.text_area("الوصف (اختياري)")
        source = st.text_input("المصدر (مثال: خمسات)")
        price = st.number_input("السعر", min_value=0.0, step=1.0)
        if st.form_submit_button("حفظ"):
            try:
                company.add_task({"title": title, "description": description,
                                  "source": source, "price": price})
                st.success("تمت إضافة المهمة")
                st.rerun()
            except ValidationError as exc:
                fail(exc)

    tasks = company.db.list_tasks()
    if tasks:
        with st.expander("تحديث مهمة"):
            options = {f"{t['id']} — {t['title']}": t["id"] for t in tasks}
            choice = st.selectbox("اختر المهمة", list(options), key="edit_task")
            new_status = st.selectbox("الحالة الجديدة", TASK_STATUSES,
                                      format_func=lambda v: ar(TASK_AR, v), key="edit_task_status")
            agents = [a["name"] for a in company.db.list_agents()]
            agent = st.selectbox("إسناد إلى وكيل", ["—", *agents],
                                 format_func=lambda v: v if v == "—" else ar(AGENT_AR, v))
            col1, col2 = st.columns(2)
            if col1.button("حفظ التحديث"):
                data = {"status": new_status}
                if agent != "—":
                    data["agent"] = agent
                company.update_task(options[choice], data)
                st.rerun()
            sure = col2.checkbox("أؤكد الحذف", key="del_task_ok")
            if col2.button("حذف المهمة") and sure:
                company.delete_task(options[choice])
                st.rerun()


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
    "العملاء": page_clients,
    "المشاريع": page_projects,
    "المهام": page_tasks,
    "الحسابات": page_finance,
    "الإعدادات": page_settings,
}


def main() -> None:
    st.markdown(RTL_CSS, unsafe_allow_html=True)
    st.title("🤖 AICompanyOS")
    company = get_company()
    page = st.sidebar.radio("القائمة", list(PAGES))
    PAGES[page](company)


main()
