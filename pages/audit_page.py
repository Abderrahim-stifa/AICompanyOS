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


def paginate_audit_logs(logs: pd.DataFrame, page: int, page_size: int = 20) -> pd.DataFrame:
    """Return one 1-based page from an already filtered audit frame."""
    if page_size < 1:
        raise ValueError("page_size must be positive")
    total_pages = max(1, (len(logs) + page_size - 1) // page_size)
    safe_page = min(max(int(page), 1), total_pages)
    start = (safe_page - 1) * page_size
    return logs.iloc[start:start + page_size].copy()


def audit_logs_to_csv(logs: pd.DataFrame) -> bytes:
    """Serialize audit rows as Excel-friendly UTF-8 CSV with BOM."""
    return logs.to_csv(index=False).encode("utf-8-sig")


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
    total_records = len(filtered_logs)
    st.metric("عدد السجلات", total_records)
    page_size = 20
    total_pages = max(1, (total_records + page_size - 1) // page_size)
    page_col1, page_col2, page_col3 = st.columns([1, 2, 1])
    with page_col2:
        current_page = int(st.number_input(
            "الصفحة", min_value=1, max_value=total_pages, value=1,
            step=1, key="audit_current_page",
        ))
    start = (current_page - 1) * page_size
    end = start + page_size
    page_logs = paginate_audit_logs(filtered_logs, current_page, page_size)
    if total_records:
        st.caption(
            f"عرض السجلات {start + 1} - {min(end, total_records)} "
            f"من أصل {total_records} · الصفحة {current_page}/{total_pages}"
        )
    else:
        st.caption("لا توجد سجلات مطابقة للفلاتر.")
    csv_data = audit_logs_to_csv(page_logs)
    st.download_button(
        "⬇️ تنزيل CSV", csv_data,
        f"audit_page_{current_page}.csv", "text/csv",
    )

    for record_number, (_, row) in enumerate(page_logs.iterrows(), start=start + 1):
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
