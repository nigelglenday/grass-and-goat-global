"""Period index helpers.

A forecast is indexed by month-end dates. We also carry quarter and year
labels for rollups. Everything downstream joins on the `month_index`
(integer 0..N-1) to avoid date-type pitfalls in numpy.
"""

from __future__ import annotations

from datetime import date

import pandas as pd


def month_index(start: date, periods: int) -> pd.DataFrame:
    """Return a DataFrame with columns:
    month_index, month (first-of-month date), month_end, quarter, year, year_offset.
    """
    months = pd.date_range(
        start=pd.Timestamp(start).to_period("M").to_timestamp(),
        periods=periods,
        freq="MS",
    )
    df = pd.DataFrame({"month": months})
    df["month_index"] = range(periods)
    df["month_end"] = df["month"] + pd.offsets.MonthEnd(0)
    df["quarter"] = df["month"].dt.to_period("Q").astype(str)
    df["year"] = df["month"].dt.year
    df["year_offset"] = df["year"] - df["year"].iloc[0]
    df["label"] = df["month"].dt.strftime("%b-%y")
    return df


def quarter_to_month_index(quarter: str, periods_df: pd.DataFrame) -> int:
    """Return the month_index of the first month in a YYYY-QN quarter,
    or -1 if the quarter is before the forecast window.
    Cohorts landing before the forecast start are still counted on the
    first forecast month (they're just already live going in).
    """
    qstart = pd.Period(quarter, freq="Q").to_timestamp()
    matches = periods_df.index[periods_df["month"] >= qstart]
    if len(matches) == 0:
        return -1  # cohort is after the forecast ends
    # If the quarter starts before the first forecast month, land it at month 0
    first_month = periods_df["month"].iloc[0]
    if qstart < first_month:
        return 0
    return int(matches[0])
