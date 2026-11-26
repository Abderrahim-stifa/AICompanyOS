"""Human-readable audit trail with filtering and CSV export."""
import json
from datetime import date

import pandas as pd
import streamlit as st

from core.date_filters import inclusive_end_date
from core.pagination import paginate


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
            start = pd.Timestamp(date_from).tz_localize("UTC")
            filtered = filtered[timestamps.loc[filtered.index] >= start]
            timestamps = pd.to_datetime(filtered["created_at"], errors="coerce", utc=True)
        if date_to is not None:
            end = inclusive_end_date(date_to).tz_localize("UTC")
            filtered = filtered[timestamps.loc[filtered.index] <= end]
    return filtered


def paginate_audit_logs(logs: pd.DataFrame, page: int, page_size: int = 20) -> pd.DataFrame:
    """Backward-compatible wrapper around the core pagination utility."""
    return paginate(logs, page, page_size)["data"]


def audit_logs_to_csv(logs: pd.DataFrame) -> bytes:
    """Serialize audit rows as Excel-friendly UTF-8 CSV with BOM."""
    return logs.to_csv(index=False).encode("utf-8-sig")


def show_audit_page(company) -> None:
    st.markdown("""
    <style>
    .st-key-audit-page {background:#f5f7ff;color:#172044;padding:22px 24px;border:1px solid #dce2f4;border-radius:18px;box-shadow:0 12px 32px #050d2518;}
    .st-key-audit-page h1,.st-key-audit-page h2,.st-key-audit-page h3,
    .st-key-audit-page p,.st-key-audit-page label,.st-key-audit-page [data-testid="stMarkdownContainer"] {color:#172044 !important;}
    .st-key-audit-page [data-testid="stMetric"] {background:linear-gradient(135deg,#fff,#eef1ff);border:1px solid #dce2f4;box-shadow:0 5px 16px #25366b12;}
    .st-key-audit-page [data-testid="stMetricLabel"],.st-key-audit-page [data-testid="stMetricValue"] {color:#28345f !important;}
    .st-key-audit-page [data-testid="stExpander"] {background:#fff;border:1px solid #dce2f4;}
    .st-key-audit-page [data-testid="stExpander"] summary,.st-key-audit-page [data-testid="stExpander"] summary p {color:#172044 !important;}
    .st-key-audit-page .stTextInput input,.st-key-audit-page .stDateInput input,
    .st-key-audit-page .stSelectbox [data-baseweb="select"] {background:#fff;color:#172044;border:1px solid #cbd4eb;}
    .st-key-audit-page .stButton button,.st-key-audit-page .stDownloadButton button {background:linear-gradient(110deg,#5b3cdd,#315fe8);color:#fff;}
    </style>
    """, unsafe_allow_html=True)
    with st.container(key="audit-page"):
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
        if filtered_logs.empty:
            st.info("لا توجد سجلات مطابقة للفلاتر الحالية.")
            return
    
        page_size = 20
        pagination = paginate(filtered_logs, 1, page_size)
        total_pages = pagination["total_pages"]
        page_col1, page_col2, page_col3 = st.columns([1, 2, 1])
        with page_col2:
            current_page = int(st.number_input(
                "الصفحة", min_value=1, max_value=total_pages, value=1,
                step=1, key="audit_current_page",
            ))
        pagination = paginate(filtered_logs, current_page, page_size)
        start = pagination["start"]
        page_logs = pagination["data"]
        st.caption(
            f"عرض السجلات {start + 1} - {pagination['end']} "
            f"من أصل {total_records} · الصفحة {current_page}/{total_pages}"
        )
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
    