"""Monthly P&L assembly.

Revenue → COGS → Gross Profit → S&M, R&D, G&A → EBITDA → D&A → EBIT → Net Income.

Pure function. Takes upstream frames (revenue, cogs, opex, headcount) and
returns a single monthly P&L DataFrame + an annual rollup.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .assumptions import Assumptions


def compute_pnl(
    a: Assumptions,
    revenue_monthly: pd.DataFrame,
    cogs_monthly: pd.DataFrame,
    opex_monthly: pd.DataFrame,
    headcount_monthly: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    n = len(revenue_monthly)

    m = pd.DataFrame(
        {
            "month_index": revenue_monthly["month_index"],
            "month": revenue_monthly["month"],
            "label": revenue_monthly["label"],
            "quarter": revenue_monthly["quarter"],
            "year": revenue_monthly["year"],
        }
    )

    m["revenue"] = revenue_monthly["mrr"].to_numpy()

    # COGS breakdown
    m["cogs_direct_labor"] = cogs_monthly["direct_labor_variable"].to_numpy()
    m["cogs_subcontractor"] = cogs_monthly["subcontractor"].to_numpy()
    m["cogs_hosting"] = cogs_monthly["hosting"].to_numpy()
    m["cogs_comp"] = cogs_monthly["ops_comp"].to_numpy()
    m["cogs_total"] = cogs_monthly["total_cogs"].to_numpy()
    m["gross_profit"] = m["revenue"] - m["cogs_total"]
    m["gross_margin"] = np.where(
        m["revenue"] > 0, m["gross_profit"] / m["revenue"], 0.0
    )

    # Opex by function (comp + non-comp)
    m["sm"] = (
        headcount_monthly["sm_comp"].to_numpy() + opex_monthly["sm_noncomp"].to_numpy()
    )
    m["rnd"] = (
        headcount_monthly["rnd_comp"].to_numpy() + opex_monthly["rnd_noncomp"].to_numpy()
    )
    m["ga"] = (
        headcount_monthly["ga_comp"].to_numpy() + opex_monthly["ga_noncomp"].to_numpy()
    )
    m["total_opex"] = m["sm"] + m["rnd"] + m["ga"]

    m["ebitda"] = m["gross_profit"] - m["total_opex"]

    # D&A: straight-line from capex schedule
    # Each month of capex depreciates over `depreciation_months`.
    # Compute cumulative active capex per month.
    dep_months = a.capex.depreciation_months
    monthly_capex = a.capex.monthly
    # At month i, depreciation = sum over j in [max(0, i-dep_months+1)..i] of capex/dep_months
    # Since all months equal, that simplifies: depr = min(i+1, dep_months) * capex / dep_months
    active_capex_count = np.minimum(np.arange(n) + 1, dep_months)
    m["depreciation"] = active_capex_count * (monthly_capex / dep_months)

    m["ebit"] = m["ebitda"] - m["depreciation"]
    # No taxes modeled (pre-revenue startup — assume NOLs)
    m["net_income"] = m["ebit"]
    m["operating_margin"] = np.where(m["revenue"] > 0, m["ebit"] / m["revenue"], 0.0)

    # Annual rollup
    annual = (
        m.groupby("year")
        .agg(
            revenue=("revenue", "sum"),
            cogs_total=("cogs_total", "sum"),
            gross_profit=("gross_profit", "sum"),
            sm=("sm", "sum"),
            rnd=("rnd", "sum"),
            ga=("ga", "sum"),
            total_opex=("total_opex", "sum"),
            ebitda=("ebitda", "sum"),
            depreciation=("depreciation", "sum"),
            ebit=("ebit", "sum"),
            net_income=("net_income", "sum"),
        )
        .reset_index()
    )
    annual["gross_margin"] = annual["gross_profit"] / annual["revenue"].where(
        annual["revenue"] > 0, 1
    )
    annual["operating_margin"] = annual["ebit"] / annual["revenue"].where(
        annual["revenue"] > 0, 1
    )

    return {"monthly": m, "annual": annual}
