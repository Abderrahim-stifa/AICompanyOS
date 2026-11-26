"""Human-readable audit trail with filtering and CSV export."""
import json
from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st


def _decode_snapshot(value):
    if not value:
        return None
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError):
        return {"raw": str(value)}


def filter_audit_logs(logs: pd.DataFrame, selected_user: str = "الكل",
                      date_from: date | None = None,
                      date_to: date | None = None) -> pd.DataFrame:
    """Return a filtered copy; end date is inclusive for all timestamps."""
    filtered = logs.copy()
    if filtered.empty:
        return filtered
    if selected_user != "الكل" and "user_name" in filtered.columns:
        filtered = filtered[filtered["user_name"].fillna("system") == selected_user]
    if "created_at" in filtered.columns:
        timestamps = pd.to_datetime(filtered["created_at"], errors="coerce", utc=True)
        if date_from is not None:
            start = pd.Timestamp(datetime.combine(date_from, time.min), tz="UTC")
            filtered = filtered[timestamps.loc[filtered.index] >= start]
            timestamps = pd.to_datetime(filtered["created_at"], errors="coerce", utc=True)
        if date_to is not None:
            end = pd.Timestamp(datetime.combine(date_to + timedelta(days=1), time.min), tz="UTC")
            filtered = filtered[timestamps.loc[filtered.index] < end]
    return filtered


def show_audit_page(company) -> None:
    st.title("سجل التعديلات")
    logs = company.db.list_system_logs(limit=1000)
    if not logs:
        st.info("لا توجد سجلات بعد")
        return

    frame = pd.DataFrame(logs)
    st.subheader("🔎 الفلاتر")
    users = sorted(frame.get("user_name", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
    timestamps = pd.to_datetime(frame.get("created_at"), errors="coerce", utc=True)
    valid_dates = timestamps.dropna()
    today = date.today()
    min_date = valid_dates.min().date() if not valid_dates.empty else today
    max_date = valid_dates.max().date() if not valid_dates.empty else today
    if min_date > max_date:
        min_date = max_date

    col1, col2, col3 = st.columns(3)
    with col1:
        selected_user = st.selectbox("المستخدم", ["الكل"] + users)
    with col2:
        date_from = st.date_input("من تاريخ", value=min_date)
    with col3:
        date_to = st.date_input("إلى تاريخ", value=max_date)

    if date_from > date_to:
        st.warning("تاريخ البداية يجب أن يكون قبل تاريخ النهاية أو مساوياً له.")
        return

    filtered_logs = filter_audit_logs(frame, selected_user, date_from, date_to)
    st.metric("عدد السجلات", len(filtered_logs))
    csv_data = filtered_logs.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ تنزيل CSV", csv_data, "audit_log.csv", "text/csv")

    for record_number, (_, row) in enumerate(filtered_logs.iterrows(), start=1):
        label = (f"#{record_number} | {row.get('action', 'EVENT')} | "
                 f"{row.get('entity_type') or '—'} #{row.get('entity_id') or '—'}")
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
