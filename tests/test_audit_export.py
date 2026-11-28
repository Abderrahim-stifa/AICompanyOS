"""Regression tests for audit viewer empty states and CSV exports."""
import csv
import io
from datetime import date

import pandas as pd

from pages.audit_page import audit_logs_to_csv, filter_audit_logs


def _read_csv(payload: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return reader.fieldnames or [], list(reader)


def test_filter_audit_logs_returns_empty_frame_when_no_actor_matches():
    frame = pd.DataFrame([
        {"id": 1, "user_name": "أحمد", "created_at": "2026-11-25T10:00:00Z"},
    ])

    filtered = filter_audit_logs(frame, selected_user="سارة")

    assert filtered.empty
    assert list(filtered.columns) == list(frame.columns)


def test_audit_csv_contains_headers_and_all_exported_values():
    frame = pd.DataFrame([
        {
            "id": 7,
            "action": "UPDATE",
            "user_name": "أحمد",
            "details": "تحديث بيانات العميل",
        },
        {
            "id": 8,
            "action": "CREATE",
            "user_name": "Sara",
            "details": "New project",
        },
    ])

    payload = audit_logs_to_csv(frame)
    headers, rows = _read_csv(payload)

    assert payload.startswith(b"\xef\xbb\xbf")
    assert headers == ["id", "action", "user_name", "details"]
    assert len(rows) == 2
    assert rows[0]["details"] == "تحديث بيانات العميل"
    assert rows[1]["user_name"] == "Sara"


def test_filtered_audit_csv_exports_only_matching_rows_and_keeps_arabic():
    frame = pd.DataFrame([
        {
            "id": 1,
            "action": "UPDATE",
            "user_name": "أحمد",
            "created_at": "2026-11-25T09:00:00Z",
            "details": "تعديل المهمة",
        },
        {
            "id": 2,
            "action": "DELETE",
            "user_name": "سارة",
            "created_at": "2026-11-25T10:00:00Z",
            "details": "حذف المشروع",
        },
        {
            "id": 3,
            "action": "CREATE",
            "user_name": "أحمد",
            "created_at": "2026-11-26T10:00:00Z",
            "details": "إنشاء عميل",
        },
    ])

    filtered = filter_audit_logs(
        frame,
        selected_user="أحمد",
        date_from=date(2026, 11, 25),
        date_to=date(2026, 11, 25),
    )
    headers, rows = _read_csv(audit_logs_to_csv(filtered))

    assert headers == list(frame.columns)
    assert [row["id"] for row in rows] == ["1"]
    assert rows[0]["details"] == "تعديل المهمة"
