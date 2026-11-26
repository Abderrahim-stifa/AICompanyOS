"""Date-boundary helpers for inclusive calendar date filtering."""
from datetime import datetime, time, timedelta

import pandas as pd


def inclusive_end_date(date_value):
    """Return the final representable microsecond of the supplied calendar day."""
    day = pd.Timestamp(date_value).date()
    return pd.Timestamp(datetime.combine(day + timedelta(days=1), time.min)) - pd.Timedelta(microseconds=1)
