"""Tests for inclusive end-of-day date boundaries."""
import pandas as pd

from core.date_filters import inclusive_end_date
from pages.audit_page import filter_audit_logs


def test_end_date_is_end_of_day():
    value = inclusive_end_date("2026-05-01")
    assert value.hour == 23
    assert value.minute == 59
    assert value.second == 59
    assert value.microsecond == 999999


def test_record_at_end_of_day_is_included():
    frame = pd.DataFrame([
        {"id": 1, "created_at": "2026-05-01 23:59:59.999999"},
        {"id": 2, "created_at": "2026-05-02 00:00:00"},
    ])
    result = filter_audit_logs(frame, date_to=pd.Timestamp("2026-05-01").date())
    assert result["id"].tolist() == [1]


def test_filter_includes_last_second_of_end_date():
    frame = pd.DataFrame([
        {"id": 1, "created_at": "2026-05-01T23:59:59Z"},
        {"id": 2, "created_at": "2026-05-02T00:00:00Z"},
    ])
    result = filter_audit_logs(frame, date_to=pd.Timestamp("2026-05-01").date())
    assert result["id"].tolist() == [1]
