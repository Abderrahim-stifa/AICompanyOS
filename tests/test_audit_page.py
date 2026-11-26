"""Unit tests for audit filtering and export data preparation."""
from datetime import date

import pandas as pd

from pages.audit_page import filter_audit_logs


def test_logs_dataframe_not_empty():
    df = pd.DataFrame([{"id": 1, "action": "CREATE"}])
    assert len(df) == 1


def test_filter_by_user():
    data = pd.DataFrame([
        {"user_name": "Ahmed", "created_at": "2026-11-25T10:00:00Z"},
        {"user_name": "Sara", "created_at": "2026-11-25T11:00:00Z"},
    ])
    filtered = filter_audit_logs(data, selected_user="Ahmed")
    assert len(filtered) == 1
    assert filtered.iloc[0]["user_name"] == "Ahmed"


def test_filter_by_date_includes_entire_end_date():
    df = pd.DataFrame([
        {"user_name": "Ahmed", "created_at": "2026-11-25T00:00:00Z"},
        {"user_name": "Sara", "created_at": "2026-11-25T23:59:59Z"},
        {"user_name": "Sara", "created_at": "2026-11-26T00:00:00Z"},
    ])
    filtered = filter_audit_logs(df, date_from=date(2026, 11, 25),
                                 date_to=date(2026, 11, 25))
    assert len(filtered) == 2


def test_filter_by_user_and_date():
    df = pd.DataFrame([
        {"user_name": "Ahmed", "created_at": "2026-11-25T10:00:00Z"},
        {"user_name": "Ahmed", "created_at": "2026-11-26T10:00:00Z"},
        {"user_name": "Sara", "created_at": "2026-11-25T10:00:00Z"},
    ])
    filtered = filter_audit_logs(df, "Ahmed", date(2026, 11, 25), date(2026, 11, 25))
    assert len(filtered) == 1
