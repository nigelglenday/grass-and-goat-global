"""Cohort-driven revenue engine.

Pure function. Vectorized — the MRR matrix is built as a single numpy array
(cohorts × months) so 60-month / 20-cohort runs stay under tens of ms. v2
sensitivity sweeps depend on this speed.

Model:
  For each cohort landed in month `m0` with `n` logos at ACV `A`:
    - Ramp: linear from 0 to full over `ramp_months`, then flat.
    - Logo retention: monthly rate derived from annual GRR.
    - ACV expansion (per surviving logo): monthly rate derived from NRR/GRR,
      so NRR = GRR × (1 + expansion)^12 at the annual level.
    - ACV escalator: applies to surviving ACV on each Jan-1 (price increases
      on existing book).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .assumptions import Assumptions
from .periods import month_index, quarter_to_month_index


def monthly_from_annual_rate(annual: float) -> float:
    """Convert annual rate (e.g. 0.92 GRR) to monthly equivalent."""
    return annual ** (1 / 12)


def compute_revenue(a: Assumptions) -> dict[str, pd.DataFrame]:
    """Build the cohort MRR matrix and monthly rollup.

    Returns dict with keys:
      - periods:        the month index DataFrame
      - cohort_matrix:  DataFrame [cohort × month_index] of MRR $
      - cohort_logos:   DataFrame [cohort × month_index] of surviving logo count
      - new_logos:      Series by month_index
      - monthly:        DataFrame with MRR, ARR, logos, new_logos, churned_logos,
                        expansion_mrr, churn_mrr, net_new_arr per month
    """
    periods_df = month_index(a.forecast.start_month, a.forecast.periods)
    n_periods = len(periods_df)
    cohorts = a.acquisition.cohorts
    n_cohorts = len(cohorts)

    # Monthly retention rate per logo (GRR)
    monthly_logo_retention = monthly_from_annual_rate(
        a.retention.gross_retention_annual
    )

    # Expansion on surviving ACV: NRR = GRR × (1 + exp)^12 annually
    # → 1 + exp_monthly = (NRR / GRR) ^ (1/12)
    grr = a.retention.gross_retention_annual
    nrr = a.retention.net_retention_annual
    expansion_factor_monthly = (nrr / grr) ** (1 / 12)

    # ACV escalator applied on Jan-1 anniversaries (year boundary)
    year_offsets = periods_df["year_offset"].to_numpy()
    is_jan = periods_df["month"].dt.month.to_numpy() == 1
    # escalator multiplier at each month (cumulative from cohort land)
    # Applied per-cohort below once we know the cohort's land month.

    # Pre-build month-indexed arrays
    mrr_matrix = np.zeros((n_cohorts, n_periods))
    logos_matrix = np.zeros((n_cohorts, n_periods))
    new_logos_by_month = np.zeros(n_periods)

    escalator_annual = a.pricing.acv_escalator_annual

    for ci, cohort in enumerate(cohorts):
        m0 = quarter_to_month_index(cohort.quarter, periods_df)
        if m0 < 0:
            continue  # cohort lands outside forecast window

        new_logos_by_month[m0] += cohort.new_logos

        # Build the per-cohort trajectory
        periods_remaining = n_periods - m0
        t = np.arange(periods_remaining)  # months since cohort land (0-indexed)

        # Ramp: 0..1 linearly over ramp_months, then 1. Month 0 gets 1/ramp.
        ramp = cohort.ramp_months
        if ramp <= 0:
            ramp_curve = np.ones(periods_remaining)
        else:
            ramp_curve = np.minimum((t + 1) / ramp, 1.0)

        # Logo survival: monthly_logo_retention^t
        logo_survival = monthly_logo_retention**t
        cohort_logos = cohort.new_logos * logo_survival

        # ACV trajectory per surviving logo:
        #   starts at avg_acv, grows by expansion_factor_monthly each month,
        #   and jumps by (1 + escalator_annual) on each Jan-1 crossed.
        acv_curve = np.full(periods_remaining, float(cohort.avg_acv))
        # expansion compounded month over month
        acv_curve = acv_curve * (expansion_factor_monthly**t)
        # ACV escalator on Jan-1s AFTER cohort land (not the land-month itself)
        jan_after_land = is_jan[m0:].copy()
        jan_after_land[0] = False  # don't count the cohort's own land-month Jan
        cumulative_escalations = np.cumsum(jan_after_land.astype(int))
        acv_curve = acv_curve * ((1 + escalator_annual) ** cumulative_escalations)

        # MRR = logos × ACV / 12 × ramp_curve
        cohort_mrr = cohort_logos * acv_curve / 12.0 * ramp_curve

        mrr_matrix[ci, m0:] = cohort_mrr
        logos_matrix[ci, m0:] = cohort_logos

    # Labels
    cohort_labels = [c.quarter for c in cohorts]
    month_labels = periods_df["label"].tolist()

    cohort_matrix_df = pd.DataFrame(
        mrr_matrix, index=cohort_labels, columns=month_labels
    )
    cohort_matrix_df.index.name = "cohort"

    cohort_logos_df = pd.DataFrame(
        logos_matrix, index=cohort_labels, columns=month_labels
    )
    cohort_logos_df.index.name = "cohort"

    # Monthly rollup
    mrr_by_month = mrr_matrix.sum(axis=0)
    logos_by_month = logos_matrix.sum(axis=0)

    # Churned logos = prior - current + new (this month)
    prior_logos = np.concatenate([[0.0], logos_by_month[:-1]])
    churned_logos = prior_logos + new_logos_by_month - logos_by_month
    churned_logos = np.maximum(churned_logos, 0.0)

    # Decompose MRR change into new/expansion/churn
    prior_mrr = np.concatenate([[0.0], mrr_by_month[:-1]])
    net_new_mrr = mrr_by_month - prior_mrr
    # Cohort-level new MRR in the month they land
    new_mrr = np.zeros(n_periods)
    for ci, cohort in enumerate(cohorts):
        m0 = quarter_to_month_index(cohort.quarter, periods_df)
        if m0 < 0:
            continue
        new_mrr[m0] += mrr_matrix[ci, m0]

    # Churn MRR: prior-month MRR × (1 - monthly_logo_retention)
    churn_mrr = prior_mrr * (1 - monthly_logo_retention)
    expansion_mrr = net_new_mrr - new_mrr + churn_mrr

    monthly = pd.DataFrame(
        {
            "month_index": periods_df["month_index"],
            "month": periods_df["month"],
            "label": periods_df["label"],
            "quarter": periods_df["quarter"],
            "year": periods_df["year"],
            "mrr": mrr_by_month,
            "arr": mrr_by_month * 12,
            "logos": logos_by_month,
            "new_logos": new_logos_by_month,
            "churned_logos": churned_logos,
            "new_mrr": new_mrr,
            "expansion_mrr": expansion_mrr,
            "churn_mrr": churn_mrr,
            "net_new_arr": net_new_mrr * 12,
            "arpu_monthly": np.divide(
                mrr_by_month,
                logos_by_month,
                out=np.zeros_like(mrr_by_month),
                where=logos_by_month > 0,
            ),
        }
    )
    monthly["acv"] = monthly["arpu_monthly"] * 12

    return {
        "periods": periods_df,
        "cohort_matrix": cohort_matrix_df,
        "cohort_logos": cohort_logos_df,
        "monthly": monthly,
    }
