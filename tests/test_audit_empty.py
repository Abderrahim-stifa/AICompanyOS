"""Tests for audit empty-result behavior."""
from datetime import date

import pandas as pd

from pages.audit_page import filter_audit_logs


def test_empty_logs_remain_empty_after_filtering():
    frame = pd.DataFrame(columns=["user_name", "created_at"])
    result = filter_audit_logs(frame, selected_user="Ahmed")
    assert result.empty


def test_filter_returns_empty_when_user_has_no_records():
    frame = pd.DataFrame([
        {"user_name": "Ahmed", "created_at": "2026-05-01T12:00:00Z"},
    ])
    result = filter_audit_logs(frame, selected_user="Sara", date_from=date(2026, 5, 1))
    assert result.empty
