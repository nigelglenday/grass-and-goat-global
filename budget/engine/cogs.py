"""Cost of goods sold.

Three components:
  1. Direct labor — % of revenue
  2. Subcontractor costs — % of revenue
  3. Hosting infrastructure — fixed monthly base with modest escalation

Plus operations headcount comp (already computed in headcount.py as cogs_comp).
"""

from __future__ import annotations

import pandas as pd

from .assumptions import Assumptions


def compute_cogs(
    a: Assumptions,
    revenue_monthly: pd.DataFrame,
    headcount_monthly: pd.DataFrame,
) -> pd.DataFrame:
    """Return DataFrame with direct_labor_pct, subcontractor, hosting,
    ops_comp, total_cogs per month, plus gross_profit and gross_margin."""
    m = revenue_monthly[["month_index", "month", "label", "mrr"]].copy()
    revenue = m["mrr"]  # monthly revenue = MRR

    m["direct_labor_variable"] = revenue * a.cogs.direct_labor_pct_revenue
    m["subcontractor"] = revenue * a.cogs.subcontractor_pct_revenue

    # Hosting escalates at opex escalation rate (approximates infra cost rise)
    year_offset = revenue_monthly["year"] - revenue_monthly["year"].iloc[0]
    m["hosting"] = a.cogs.hosting_monthly_base * (
        (1 + a.opex.annual_escalation) ** year_offset
    )

    m["ops_comp"] = headcount_monthly["cogs_comp"].to_numpy()

    m["total_cogs"] = (
        m["direct_labor_variable"] + m["subcontractor"] + m["hosting"] + m["ops_comp"]
    )
    m["revenue"] = revenue
    m["gross_profit"] = revenue - m["total_cogs"]
    m["gross_margin"] = m["gross_profit"] / revenue.where(revenue > 0, 1)

    return m
