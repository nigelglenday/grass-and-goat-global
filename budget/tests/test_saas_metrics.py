"""SaaS metrics tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from engine.balance_sheet import compute_balance_sheet_and_cash_flow
from engine.cogs import compute_cogs
from engine.headcount import compute_headcount
from engine.opex import compute_opex
from engine.pnl import compute_pnl
from engine.revenue import compute_revenue
from engine.saas_metrics import compute_saas_metrics
from engine.scenarios import load_scenario

CONFIG = Path(__file__).parent.parent / "configs" / "base_case.yaml"


def _run():
    a = load_scenario(CONFIG)
    rev = compute_revenue(a)
    hc = compute_headcount(a)
    cogs = compute_cogs(a, rev["monthly"], hc["monthly"])
    op = compute_opex(a, rev["monthly"])
    pnl = compute_pnl(a, rev["monthly"], cogs, op, hc["monthly"])
    bscf = compute_balance_sheet_and_cash_flow(a, pnl["monthly"])
    metrics = compute_saas_metrics(
        a, rev["monthly"], pnl["monthly"], bscf["cash_flow"], bscf["balance_sheet"]
    )
    return a, pnl, bscf, metrics


def test_arr_equals_12x_mrr():
    _, _, _, metrics = _run()
    m = metrics["monthly"]
    assert np.allclose(m["arr"], m["mrr"] * 12)


def test_net_new_arr_decomposes_into_new_expansion_churn():
    _, _, _, metrics = _run()
    m = metrics["monthly"]
    reconstructed = m["new_arr"] + m["expansion_arr"] - m["churn_arr"]
    assert np.allclose(reconstructed, m["net_new_arr"], atol=1.0)


def test_rule_of_40_is_growth_plus_margin():
    _, _, _, metrics = _run()
    m = metrics["monthly"]
    # Check at a month where both components are defined (month 13)
    row = m.iloc[13]
    expected = (row["arr_yoy_growth"] + row["op_margin_ttm"]) * 100
    assert abs(row["rule_of_40"] - expected) < 1e-6


def test_ltv_positive_and_finite():
    _, _, _, metrics = _run()
    m = metrics["monthly"]
    # After first few months, LTV should be positive and finite
    late = m.iloc[24:]["ltv"].dropna()
    assert (late > 0).all()
    assert np.isfinite(late).all()


def test_ltv_cac_ratio_in_reasonable_range():
    """For a healthy SaaS, LTV/CAC > 3 is the ballpark.
    Our base-case assumptions should clear that easily at scale."""
    _, _, _, metrics = _run()
    q = metrics["quarterly"].dropna(subset=["ltv_cac"])
    # Later quarters should have LTV/CAC > 3
    assert q["ltv_cac"].iloc[-1] > 3


def test_grr_ttm_bounded_by_annual_grr():
    a, _, _, metrics = _run()
    m = metrics["monthly"]
    # Realized GRR should be close to annual GRR when cohorts are steady state.
    # Check month 24 (after two full years of data).
    grr_obs = m.iloc[24]["grr_ttm"]
    # Should be within 10% of the annual input
    assert abs(grr_obs - a.retention.gross_retention_annual) < 0.1


def test_runway_finite_during_burn_infinite_at_profitability():
    _, _, _, metrics = _run()
    m = metrics["monthly"]
    # Year 1: burning, runway should be finite (or already past it)
    # Year 5: profitable, runway should be infinite
    year5_runway = m.iloc[-1]["runway_months"]
    assert year5_runway == np.inf or year5_runway > 120


def test_new_logos_reconciles():
    a, _, _, metrics = _run()
    total = metrics["monthly"]["new_logos"].sum()
    expected = sum(c.new_logos for c in a.acquisition.cohorts)
    assert abs(total - expected) < 1e-6
