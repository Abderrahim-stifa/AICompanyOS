"""Project-linked workspaces for domain-specific deliverables and reviews."""
from __future__ import annotations

import streamlit as st

from core.auth_context import CurrentUser
from core.database import Database
from core.deliverables import DOMAINS, DeliverableStore
from core.page_views import get_company

st.title("مساحات العمل والمخرجات")
st.caption(
    "أنشئ مخرجات مرتبطة بمشروع ومسؤول، واحتفظ بالإصدارات والمصادر والافتراضات "
    "وسجل المراجعة. الاعتماد هنا توثيق مراجعة داخلية وليس اعتماداً مهنياً أو قانونياً."
)

company = get_company()
store = DeliverableStore(company.db)
store.init()
projects = company.db.list_projects()
if not projects:
    st.info("أنشئ مشروعاً أولاً من صفحة المشاريع حتى تربط به المخرجات.")
    st.stop()

project_map = {f"#{p['id']} — {p['name']}": p["id"] for p in projects}
project_label = st.selectbox("المشروع", list(project_map), key="deliverable_project")
project_id = project_map[project_label]
domain_labels = {label: key for key, label in DOMAINS.items()}

with st.expander("إنشاء مخرج جديد", expanded=True):
    with st.form("create_deliverable_form", clear_on_submit=True):
        domain_label = st.selectbox("مجال العمل", list(domain_labels))
        title = st.text_input("عنوان المخرج", max_chars=200)
        content = st.text_area("المحتوى أو المواصفات أو التحليل", height=180, max_chars=20000)
        owner = st.text_input("المسؤول", value=CurrentUser.get_username(), max_chars=100)
        sources_raw = st.text_area("المصادر (مصدر في كل سطر)", height=70)
        assumptions_raw = st.text_area("الافتراضات (افتراض في كل سطر)", height=70)
        submitted = st.form_submit_button("حفظ الإصدار الأول", type="primary")
    if submitted:
        try:
            item = store.create(
                project_id,domain_labels[domain_label],title,content,owner,
                [x.strip() for x in sources_raw.splitlines() if x.strip()],
                [x.strip() for x in assumptions_raw.splitlines() if x.strip()],
            )
            st.success(f"تم إنشاء المخرج #{item['id']} — الإصدار 1.")
            st.rerun()
        except (ValueError, LookupError) as exc:
            st.error(str(exc))

items = store.list(project_id)
st.subheader("المخرجات المسجلة لهذا المشروع")
if not items:
    st.info("لا توجد مخرجات لهذا المشروع بعد.")
for item in items:
    label = f"#{item['id']} · {DOMAINS[item['domain']]} · {item['title']} · v{item['version']} · {item['status']}"
    with st.expander(label, expanded=False):
        st.caption(f"المسؤول: {item['owner']} · آخر تحديث: {item['updated_at']}")
        st.write(item["content"])
        st.markdown("**المصادر**")
        if item["sources"]:
            for source in item["sources"]:
                st.markdown(f"- {source}")
        else:
            st.caption("لم تُسجل مصادر.")
        st.markdown("**الافتراضات**")
        if item["assumptions"]:
            for assumption in item["assumptions"]:
                st.markdown(f"- {assumption}")
        else:
            st.caption("لم تُسجل افتراضات.")
        if item["reviewer"]:
            st.caption(f"المراجع: {item['reviewer']} · الملاحظة: {item['review_note'] or '—'}")

        with st.form(f"revise_deliverable_{item['id']}"):
            st.markdown("**إنشاء إصدار جديد**")
            new_title = st.text_input("العنوان الجديد", value=item["title"], key=f"title_{item['id']}")
            new_content = st.text_area("المحتوى الجديد", value=item["content"], height=130, key=f"content_{item['id']}")
            new_owner = st.text_input("المسؤول عن الإصدار", value=CurrentUser.get_username(), key=f"owner_{item['id']}")
            new_sources = st.text_area("المصادر الجديدة", value="\n".join(item["sources"]), key=f"sources_{item['id']}")
            new_assumptions = st.text_area("الافتراضات الجديدة", value="\n".join(item["assumptions"]), key=f"assumptions_{item['id']}")
            revise = st.form_submit_button("حفظ كإصدار جديد")
        if revise:
            try:
                store.revise(item["id"],new_title,new_content,new_owner,
                    [x.strip() for x in new_sources.splitlines() if x.strip()],
                    [x.strip() for x in new_assumptions.splitlines() if x.strip()])
                st.success("تم حفظ إصدار جديد وإرجاع حالته إلى مسودة.")
                st.rerun()
            except (ValueError, LookupError) as exc:
                st.error(str(exc))

        st.markdown("**المراجعة والاعتماد الداخلي**")
        reviewer = st.text_input("اسم المراجع", value=CurrentUser.get_username(), key=f"reviewer_{item['id']}")
        review_note = st.text_area("ملاحظة المراجعة", key=f"note_{item['id']}")
        c1,c2,c3 = st.columns(3)
        if c1.button("إرسال للمراجعة", key=f"review_{item['id']}"):
            try:
                store.set_status(item["id"],"in_review",reviewer,review_note)
                st.rerun()
            except (ValueError, LookupError) as exc:
                st.error(str(exc))
        if c2.button("اعتماد داخلي", key=f"approve_{item['id']}", disabled=item["status"]!="in_review"):
            try:
                store.set_status(item["id"],"approved",reviewer,review_note)
                st.rerun()
            except (ValueError, LookupError) as exc:
                st.error(str(exc))
        if c3.button("رفض", key=f"reject_{item['id']}", disabled=item["status"]!="in_review"):
            try:
                store.set_status(item["id"],"rejected",reviewer,review_note)
                st.rerun()
            except (ValueError, LookupError) as exc:
                st.error(str(exc))

        versions = store.versions(item["id"])
        st.markdown("**سجل الإصدارات**")
        for version in versions:
            st.caption(f"v{version['version']} · {version['owner']} · {version['created_at']}")
            with st.expander(f"عرض الإصدار {version['version']}"):
                st.write(version["title"])
                st.write(version["content"])
                st.write("المصادر:", version["sources_json"])
                st.write("الافتراضات:", version["assumptions_json"])

        if item["domain"] == "architecture":
            st.warning("هذا تصور أولي فقط؛ لا يصلح للتنفيذ أو الترخيص دون مراجعة واعتماد مهني من معماري/مهندس مؤهل.")
        elif item["domain"] == "feasibility":
            st.warning("ميّز البيانات السوقية الموثقة عن التقديرات والافتراضات؛ لا تعتبر الأرقام غير المتحققة بيانات فعلية.")
        elif item["domain"] == "design":
            st.info("سجل حقوق الأصول والمقاسات وصيغ التسليم قبل اعتبار التصميم جاهزاً للإنتاج.")
        elif item["domain"] == "software":
            st.info("اربط المخرجات بالمتطلبات والقرارات المعمارية والاختبارات ودليل الإصدار قبل التسليم.")
