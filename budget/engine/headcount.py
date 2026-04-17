"""Headcount + comp forecast.

Pure function. Two sources of comp:
  1. Existing base (14 people @ $125K/mo total) — grows on Jan-1 anniversaries.
  2. Hire plan — each hire starts in their month, adds their salary/12 to
     monthly comp thereafter; also gets annual Jan-1 raises.

Output bucketed by department so downstream P&L can classify S&M / R&D / G&A.
Benefits are grossed up per `benefits_rate`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .assumptions import Assumptions
from .periods import month_index

# Map department keys to P&L functional categories.
DEPT_TO_FUNCTION = {
    "operations": "cogs",     # direct labor for goat ops = COGS
    "engineering": "rnd",
    "sales": "sm",
    "marketing": "sm",
    "ga": "ga",
}


def compute_headcount(a: Assumptions) -> dict[str, pd.DataFrame]:
    """Return dict with:
      - monthly:     month_index, base_comp, benefits, total_comp,
                     cogs_comp, sm_comp, rnd_comp, ga_comp, headcount
      - roster:      per-hire monthly comp rows (for Excel detail)
    """
    periods_df = month_index(a.forecast.start_month, a.forecast.periods)
    n_periods = len(periods_df)
    years = periods_df["year"].to_numpy()
    is_jan = periods_df["month"].dt.month.to_numpy() == 1

    benefits_rate = a.headcount.benefits_rate
    raise_rate = a.headcount.annual_raise

    # Existing base — already grossed UP before benefits? YAML says
    # existing_monthly_comp is base payroll pre-benefits. Applies Jan-1 raises
    # after year 0 (first Jan in forecast window).
    # Treat existing base as "operations" for COGS classification (it's mostly
    # goat-op staff in a 14-person company).
    existing_base = np.full(n_periods, a.headcount.existing_monthly_comp)
    # apply raises at each Jan after the first forecast month
    jan_mask = is_jan.copy()
    jan_mask[0] = False  # don't raise on month 0 (starting comp is as-is)
    raise_count = np.cumsum(jan_mask.astype(int))
    existing_base = existing_base * ((1 + raise_rate) ** raise_count)

    # Hire plan — build per-hire monthly comp vector and bucket by dept
    dept_comp = {k: np.zeros(n_periods) for k in set(DEPT_TO_FUNCTION.values())}
    # also existing-base goes into cogs bucket (operations default)
    dept_comp["cogs"] = dept_comp["cogs"] + existing_base

    roster_rows = []
    headcount_count = np.full(n_periods, a.headcount.existing_count, dtype=float)

    for hire in a.headcount.plan:
        # Hire starts when their start month >= forecast start
        start_ts = pd.Timestamp(hire.start).to_period("M").to_timestamp()
        mask = periods_df["month"] >= start_ts
        start_idx = int(np.argmax(mask.to_numpy())) if mask.any() else -1
        if start_idx < 0:
            continue

        monthly_salary = hire.salary / 12
        # Apply Jan-1 raises from their start
        raises_post_hire = jan_mask.copy()
        raises_post_hire[:start_idx] = False
        raises_count = np.cumsum(raises_post_hire.astype(int))
        salary_trajectory = np.where(
            periods_df["month"].to_numpy() >= np.datetime64(start_ts),
            monthly_salary * ((1 + raise_rate) ** raises_count),
            0.0,
        )

        # Head count increment
        headcount_count[start_idx:] += 1.0

        function = DEPT_TO_FUNCTION.get(hire.dept, "ga")
        dept_comp[function] = dept_comp[function] + salary_trajectory

        roster_rows.append(
            pd.DataFrame(
                {
                    "month": periods_df["month"],
                    "role": hire.role,
                    "dept": hire.dept,
                    "function": function,
                    "monthly_salary": salary_trajectory,
                }
            )
        )

    # Roll up
    total_base = np.zeros(n_periods)
    for arr in dept_comp.values():
        total_base = total_base + arr
    total_benefits = total_base * benefits_rate
    total_comp = total_base + total_benefits

    monthly = pd.DataFrame(
        {
            "month_index": periods_df["month_index"],
            "month": periods_df["month"],
            "label": periods_df["label"],
            "headcount": headcount_count,
            "base_comp": total_base,
            "benefits": total_benefits,
            "total_comp": total_comp,
            "cogs_comp": dept_comp["cogs"] * (1 + benefits_rate),
            "sm_comp": dept_comp["sm"] * (1 + benefits_rate),
            "rnd_comp": dept_comp["rnd"] * (1 + benefits_rate),
            "ga_comp": dept_comp["ga"] * (1 + benefits_rate),
        }
    )

    roster = (
        pd.concat(roster_rows, ignore_index=True)
        if roster_rows
        else pd.DataFrame(columns=["month", "role", "dept", "function", "monthly_salary"])
    )

    return {"monthly": monthly, "roster": roster}
