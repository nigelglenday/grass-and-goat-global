"""Orchestrator + ForecastResult — purity & addressability tests.

These are the v2 readiness checks. If they break, sensitivity sweeps will
not work correctly.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from engine.assumptions import get_by_path, set_by_path
from engine.forecast import run_forecast
from engine.scenarios import load_scenario

CONFIG = Path(__file__).parent.parent / "configs" / "base_case.yaml"


def test_run_forecast_is_deterministic():
    """Same assumptions -> same ForecastResult.id."""
    a = load_scenario(CONFIG)
    r1 = run_forecast(a)
    r2 = run_forecast(a)
    assert r1.id == r2.id
    # And same numeric outputs
    assert np.allclose(r1.pnl["monthly"]["revenue"], r2.pnl["monthly"]["revenue"])


def test_run_forecast_fast_enough_for_sensitivity():
    """60-month run under 100ms so v2 can do 1000-run sweeps in under 2min."""
    a = load_scenario(CONFIG)
    # Warm up
    run_forecast(a)
    t0 = time.time()
    for _ in range(10):
        run_forecast(a)
    avg_ms = (time.time() - t0) * 100  # /10, *1000
    assert avg_ms < 100, f"avg run time {avg_ms:.1f}ms exceeds 100ms budget"


def test_assumption_mutation_flows_to_result():
    """set_by_path on a frozen assumptions produces a different result.id and
    a different numeric output. Original is unchanged."""
    a = load_scenario(CONFIG)
    r_base = run_forecast(a)
    a2 = set_by_path(a, "retention.net_retention_annual", 1.20)
    r_override = run_forecast(a2)

    assert r_base.id != r_override.id
    # Original assumption still 1.10
    assert get_by_path(a, "retention.net_retention_annual") == 1.10
    # Year-5 ARR should be higher under higher NRR
    assert r_override.get("arr", "2030-12") > r_base.get("arr", "2030-12")


def test_result_get_by_period_monthly():
    a = load_scenario(CONFIG)
    r = run_forecast(a)
    arr_jan26 = r.get("arr", "2026-01")
    arr_dec30 = r.get("arr", "2030-12")
    assert arr_jan26 >= 0
    assert arr_dec30 > arr_jan26  # growing business


def test_result_get_by_period_quarterly():
    a = load_scenario(CONFIG)
    r = run_forecast(a)
    r40_28q4 = r.get("rule_of_40", "2028-Q4")
    assert np.isfinite(r40_28q4)


def test_result_get_by_year_uses_annual_rollup_for_pnl_metrics():
    a = load_scenario(CONFIG)
    r = run_forecast(a)
    ebitda_2030 = r.get("ebitda", "2030")
    # Compare against manual monthly sum
    expected = r.pnl["monthly"].query("year == 2030")["ebitda"].sum()
    assert abs(ebitda_2030 - expected) < 1.0


def test_v2_inner_loop_spot_check():
    """The target v2 sensitivity loop — 10 mutations + reads should be < 1 sec."""
    a = load_scenario(CONFIG)
    paths = [
        "retention.net_retention_annual",
        "retention.gross_retention_annual",
        "pricing.acv_escalator_annual",
        "cogs.direct_labor_pct_revenue",
        "cogs.subcontractor_pct_revenue",
        "opex.rent_monthly",
        "opex.software_monthly",
        "acquisition.s_and_m_monthly_base",
        "capex.monthly",
        "headcount.annual_raise",
    ]
    t0 = time.time()
    for p in paths:
        base = get_by_path(a, p)
        a2 = set_by_path(a, p, base * 1.1)
        r = run_forecast(a2)
        _ = r.get("ebitda", "2030")
    dt = time.time() - t0
    assert dt < 1.0, f"10 sensitivity runs took {dt:.2f}s (>1s budget)"
