"""Human-readable audit trail with before/after snapshots."""
import json

import streamlit as st


def _decode_snapshot(value):
    if not value:
        return None
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError):
        return {"raw": str(value)}


def show_audit_page(company) -> None:
    st.title("سجل التعديلات")
    logs = company.db.list_system_logs(limit=1000)
    if not logs:
        st.info("لا توجد سجلات بعد")
        return

    for row in logs:
        label = f"{row.get('action', 'EVENT')} | {row.get('entity_type') or '—'} #{row.get('entity_id') or '—'}"
        with st.expander(label):
            st.write(f"المستخدم: {row.get('user_name') or 'system'}")
            st.write(f"التاريخ: {row.get('created_at') or '—'}")
            if row.get("details"):
                st.caption(row["details"])
            before, after = st.columns(2)
            with before:
                st.subheader("القيم السابقة")
                snapshot = _decode_snapshot(row.get("old_values"))
                if snapshot is not None:
                    st.json(snapshot)
                else:
                    st.caption("لا توجد قيم سابقة.")
            with after:
                st.subheader("القيم الجديدة")
                snapshot = _decode_snapshot(row.get("new_values"))
                if snapshot is not None:
                    st.json(snapshot)
                else:
                    st.caption("لا توجد قيم جديدة.")
