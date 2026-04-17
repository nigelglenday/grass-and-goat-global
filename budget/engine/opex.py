"""Non-comp operating expenses.

Monthly base by category, escalated annually. Each category is tagged with
its P&L function (sm / rnd / ga / cogs). Sales & marketing also includes
acquisition.s_and_m_monthly_base and variable per-logo costs (handled here
because S&M is where they belong on the P&L even though they're driven off
acquisition assumptions).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .assumptions import Assumptions


# Bucket each category into a P&L function
OPEX_CATEGORY_FUNCTION = {
    "rent": "ga",
    "utilities": "ga",
    "insurance": "ga",
    "office_supplies": "ga",
    "software": "ga",
    "professional_fees": "ga",
    "travel": "sm",
    "misc": "ga",
}


def compute_opex(
    a: Assumptions,
    revenue_monthly: pd.DataFrame,
) -> pd.DataFrame:
    """Return DataFrame with per-category monthly opex, plus s_and_m variable."""
    n = len(revenue_monthly)
    year_offset = (revenue_monthly["year"] - revenue_monthly["year"].iloc[0]).to_numpy()
    escalator = (1 + a.opex.annual_escalation) ** year_offset

    base = {
        "rent": a.opex.rent_monthly,
        "utilities": a.opex.utilities_monthly,
        "insurance": a.opex.insurance_monthly,
        "office_supplies": a.opex.office_supplies_monthly,
        "software": a.opex.software_monthly,
        "professional_fees": a.opex.professional_fees_monthly,
        "travel": a.opex.travel_monthly,
        "misc": a.opex.misc_monthly,
    }

    df = pd.DataFrame(
        {"month_index": revenue_monthly["month_index"], "month": revenue_monthly["month"]}
    )
    for cat, val in base.items():
        df[cat] = val * escalator

    # S&M base (fixed programmatic spend) + variable per-logo (one-time CAC)
    df["sm_base"] = a.acquisition.s_and_m_monthly_base * escalator
    df["sm_variable"] = (
        revenue_monthly["new_logos"].to_numpy() * a.acquisition.s_and_m_variable_per_logo
    )

    # Roll into functional buckets
    sm_cols = ["travel", "sm_base", "sm_variable"]
    ga_cols = ["rent", "utilities", "insurance", "office_supplies",
               "software", "professional_fees", "misc"]

    df["sm_noncomp"] = df[sm_cols].sum(axis=1)
    df["ga_noncomp"] = df[ga_cols].sum(axis=1)
    df["rnd_noncomp"] = 0.0  # no R&D non-comp in this model (keep the hook)

    df["total_noncomp_opex"] = df["sm_noncomp"] + df["ga_noncomp"] + df["rnd_noncomp"]

    return df
