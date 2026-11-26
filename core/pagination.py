"""Reusable DataFrame pagination helpers."""
def paginate(dataframe, page_number, page_size):
    """Return a 1-based page and pagination metadata without mutating input."""
    if page_size < 1:
        raise ValueError("page_size must be positive")
    if page_number < 1:
        raise ValueError("page_number must be positive")

    total_records = len(dataframe)
    total_pages = max(1, (total_records + page_size - 1) // page_size)
    safe_page = min(page_number, total_pages)
    start_index = (safe_page - 1) * page_size
    end_index = start_index + page_size
    return {
        "data": dataframe.iloc[start_index:end_index].copy(),
        "total_records": total_records,
        "total_pages": total_pages,
        "start": start_index,
        "end": min(end_index, total_records),
    }
