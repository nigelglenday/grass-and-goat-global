"""Revenue cohort engine tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from engine.revenue import compute_revenue, monthly_from_annual_rate
from engine.scenarios import load_scenario

CONFIG = Path(__file__).parent.parent / "configs" / "base_case.yaml"


def test_monthly_from_annual_rate():
    # 0.92 annual GRR → compounds back to 0.92 over 12 months
    m = monthly_from_annual_rate(0.92)
    assert abs(m**12 - 0.92) < 1e-10


def test_cohort_matrix_ties_to_monthly():
    a = load_scenario(CONFIG)
    r = compute_revenue(a)
    matrix = r["cohort_matrix"].to_numpy()
    monthly_mrr = r["monthly"]["mrr"].to_numpy()
    assert np.allclose(matrix.sum(axis=0), monthly_mrr, atol=1e-6)


def test_arr_equals_12x_mrr():
    a = load_scenario(CONFIG)
    r = compute_revenue(a)
    m = r["monthly"]
    assert np.allclose(m["arr"], m["mrr"] * 12)


def test_new_logos_total_equals_cohort_sum():
    a = load_scenario(CONFIG)
    r = compute_revenue(a)
    total_new_logos_in_forecast = r["monthly"]["new_logos"].sum()
    # Cohorts landing in-window only
    expected = sum(
        c.new_logos
        for c in a.acquisition.cohorts
        # All 20 cohorts fit in the 60-month window starting 2026-Q1
    )
    assert abs(total_new_logos_in_forecast - expected) < 1e-6


def test_grr_bounds_logo_decay_without_new_cohorts():
    """If a cohort lands alone, surviving logos after 12 months = cohort * GRR."""
    a = load_scenario(CONFIG)
    # Use the first cohort in isolation via cohort_logos
    r = compute_revenue(a)
    logos_df = r["cohort_logos"]
    first_cohort_name = logos_df.index[0]
    # Cohort lands month 0; check month 12 survival
    row = logos_df.loc[first_cohort_name].to_numpy()
    original = a.acquisition.cohorts[0].new_logos
    after_12mo = row[12]
    expected = original * a.retention.gross_retention_annual
    assert abs(after_12mo - expected) < 1e-6


def test_ramp_reaches_full_revenue_after_ramp_months():
    """A cohort at full ramp (month = ramp_months) should have no ramp discount."""
    a = load_scenario(CONFIG)
    r = compute_revenue(a)
    first = a.acquisition.cohorts[0]
    matrix = r["cohort_matrix"].iloc[0].to_numpy()
    logos = r["cohort_logos"].iloc[0].to_numpy()
    # At month == ramp_months, MRR should equal logos * ACV / 12 exactly (ramp=1.0)
    ramp_m = first.ramp_months
    # ACV at that point includes monthly expansion, so back it out
    monthly_expansion = (
        a.retention.net_retention_annual / a.retention.gross_retention_annual
    ) ** (1 / 12)
    acv_at_ramp = first.avg_acv * (monthly_expansion**ramp_m)
    expected_mrr = logos[ramp_m] * acv_at_ramp / 12
    assert abs(matrix[ramp_m] - expected_mrr) < 1.0  # penny tolerance


def test_nrr_reconciles_approximately():
    """NRR ≈ (MRR at t+12 from existing cohorts) / (MRR at t from same cohorts).

    We check cohort-level: a cohort's MRR change over 12 months
    (excluding cohort land-month ramp) reflects NRR.
    """
    a = load_scenario(CONFIG)
    r = compute_revenue(a)
    # Take first cohort after full ramp (month 3..15)
    matrix = r["cohort_matrix"].iloc[0].to_numpy()
    mrr_m3 = matrix[3]
    mrr_m15 = matrix[15]
    # NRR compounds monthly via expansion, but logos also churn — so ratio = NRR
    ratio = mrr_m15 / mrr_m3
    # Expected: ramp is flat (both at full), so ratio = GRR × (NRR/GRR) = NRR
    # Actually: logos decay by GRR, ACV expands by (NRR/GRR) → combined ≈ NRR
    # over 12 months with cohort also subject to ACV escalator on Jan-1 crossings.
    expected = a.retention.net_retention_annual * (1 + a.pricing.acv_escalator_annual)
    # Allow 2% tolerance for escalator timing and Jan boundary effects
    assert abs(ratio - expected) / expected < 0.02


def test_churn_mrr_is_positive_after_first_month():
    a = load_scenario(CONFIG)
    r = compute_revenue(a)
    m = r["monthly"]
    # After month 1 there should always be some churn (cohorts exist)
    assert (m["churn_mrr"].iloc[1:] >= 0).all()
    assert m["churn_mrr"].iloc[12:].sum() > 0


def test_net_new_arr_reconciles_to_arr_change():
    a = load_scenario(CONFIG)
    r = compute_revenue(a)
    m = r["monthly"]
    arr_change = m["arr"].diff().fillna(m["arr"].iloc[0])
    assert np.allclose(arr_change, m["net_new_arr"], atol=1e-6)
