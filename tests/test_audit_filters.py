"""Behavioral tests for audit date-range filtering."""
from datetime import date

import pandas as pd

from pages.audit_page import filter_audit_logs


def test_date_range_returns_only_records_inside_interval():
    frame = pd.DataFrame([
        {"id": 1, "created_at": "2026-01-01T12:00:00Z"},
        {"id": 2, "created_at": "2026-06-15T12:00:00Z"},
        {"id": 3, "created_at": "2026-12-01T12:00:00Z"},
    ])
    result = filter_audit_logs(
        frame, date_from=date(2026, 5, 1), date_to=date(2026, 7, 1)
    )
    assert result["id"].tolist() == [2]


def test_date_range_includes_both_calendar_day_boundaries():
    frame = pd.DataFrame([
        {"id": 1, "created_at": "2026-05-01T00:00:00Z"},
        {"id": 2, "created_at": "2026-05-01T23:59:59Z"},
        {"id": 3, "created_at": "2026-05-02T00:00:00Z"},
    ])
    result = filter_audit_logs(
        frame, date_from=date(2026, 5, 1), date_to=date(2026, 5, 1)
    )
    assert result["id"].tolist() == [1, 2]
