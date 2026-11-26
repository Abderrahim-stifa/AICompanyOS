"""Tests for audit pagination."""
import pandas as pd

from pages.audit_page import paginate_audit_logs


def test_pagination_returns_expected_slice():
    frame = pd.DataFrame({"id": list(range(1, 46))})
    result = paginate_audit_logs(frame, page=2, page_size=20)
    assert result["id"].tolist() == list(range(21, 41))


def test_pagination_clamps_out_of_range_page_and_handles_empty_data():
    frame = pd.DataFrame({"id": [1, 2, 3]})
    assert paginate_audit_logs(frame, page=99, page_size=2)["id"].tolist() == [3]
    assert paginate_audit_logs(frame.iloc[0:0], page=1).empty


def test_pagination_rejects_non_positive_page_size():
    try:
        paginate_audit_logs(pd.DataFrame({"id": [1]}), page=1, page_size=0)
    except ValueError as exc:
        assert "page_size" in str(exc)
    else:
        raise AssertionError("Expected ValueError for page_size=0")
