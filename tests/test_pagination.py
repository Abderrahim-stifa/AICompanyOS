"""Unit tests for the standalone pagination utility."""
import pandas as pd
import pytest

from core.pagination import paginate


def test_first_page():
    result = paginate(pd.DataFrame({"id": range(1, 101)}), 1, 20)
    assert result["data"]["id"].tolist() == list(range(1, 21))
    assert result["total_pages"] == 5
    assert result["start"] == 0
    assert result["end"] == 20


def test_last_page():
    result = paginate(pd.DataFrame({"id": range(1, 101)}), 5, 20)
    assert result["data"]["id"].tolist() == list(range(81, 101))


def test_partial_last_page():
    result = paginate(pd.DataFrame({"id": range(1, 93)}), 5, 20)
    assert result["data"]["id"].tolist() == list(range(81, 93))
    assert result["total_pages"] == 5
    assert result["end"] == 92


def test_empty_dataframe_has_one_empty_page():
    result = paginate(pd.DataFrame(columns=["id"]), 1, 20)
    assert result["data"].empty
    assert result["total_records"] == 0
    assert result["total_pages"] == 1
    assert result["start"] == result["end"] == 0


@pytest.mark.parametrize("page_number,page_size", [(0, 20), (1, 0), (-1, 20), (1, -2)])
def test_invalid_pagination_arguments_are_rejected(page_number, page_size):
    with pytest.raises(ValueError):
        paginate(pd.DataFrame({"id": [1]}), page_number, page_size)
