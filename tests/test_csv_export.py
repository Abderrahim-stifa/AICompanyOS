"""Tests for filtered audit CSV serialization."""
import pandas as pd

from pages.audit_page import audit_logs_to_csv


def test_csv_contains_rows_and_headers():
    frame = pd.DataFrame([
        {"action": "CREATE", "user_name": "Ahmed"},
        {"action": "DELETE", "user_name": "Sara"},
    ])
    csv_text = audit_logs_to_csv(frame).decode("utf-8-sig")
    assert "action,user_name" in csv_text
    assert "CREATE" in csv_text
    assert "DELETE" in csv_text


def test_csv_exports_only_the_filtered_rows():
    frame = pd.DataFrame([
        {"user_name": "Ahmed"},
        {"user_name": "Sara"},
    ])
    filtered = frame[frame["user_name"] == "Ahmed"]
    csv_text = audit_logs_to_csv(filtered).decode("utf-8-sig")
    assert "Ahmed" in csv_text
    assert "Sara" not in csv_text


def test_csv_preserves_arabic_and_utf8_bom():
    frame = pd.DataFrame([{"action": "إنشاء مهمة"}])
    data = audit_logs_to_csv(frame)
    assert data.startswith(b"\\xef\\xbb\\xbf")
    assert "إنشاء مهمة" in data.decode("utf-8-sig")
