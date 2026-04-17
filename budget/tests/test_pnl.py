"""P&L + headcount + opex + cogs tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from engine.cogs import compute_cogs
from engine.headcount import compute_headcount
from engine.opex import compute_opex
from engine.pnl import compute_pnl
from engine.revenue import compute_revenue
from engine.scenarios import load_scenario

CONFIG = Path(__file__).parent.parent / "configs" / "base_case.yaml"


def _run():
    a = load_scenario(CONFIG)
    rev = compute_revenue(a)
    hc = compute_headcount(a)
    cogs = compute_cogs(a, rev["monthly"], hc["monthly"])
    op = compute_opex(a, rev["monthly"])
    pnl = compute_pnl(a, rev["monthly"], cogs, op, hc["monthly"])
    return a, rev, hc, cogs, op, pnl


def test_revenue_flows_to_pnl():
    _, rev, _, _, _, pnl = _run()
    assert np.allclose(pnl["monthly"]["revenue"], rev["monthly"]["mrr"])


def test_gross_profit_is_revenue_minus_cogs():
    _, _, _, _, _, pnl = _run()
    m = pnl["monthly"]
    assert np.allclose(m["gross_profit"], m["revenue"] - m["cogs_total"])


def test_ebitda_equals_gp_minus_opex():
    _, _, _, _, _, pnl = _run()
    m = pnl["monthly"]
    assert np.allclose(m["ebitda"], m["gross_profit"] - m["total_opex"])


def test_opex_functional_sum_ties():
    _, _, _, _, _, pnl = _run()
    m = pnl["monthly"]
    assert np.allclose(m["total_opex"], m["sm"] + m["rnd"] + m["ga"])


def test_annual_sum_ties_to_monthly():
    _, _, _, _, _, pnl = _run()
    for metric in ["revenue", "cogs_total", "ebitda", "net_income"]:
        monthly_sum = pnl["monthly"].groupby("year")[metric].sum()
        annual = pnl["annual"].set_index("year")[metric]
        assert np.allclose(monthly_sum, annual), f"{metric} rollup mismatch"


def test_headcount_grows_with_plan():
    a, _, hc, _, _, _ = _run()
    m = hc["monthly"]
    assert m["headcount"].iloc[0] == a.headcount.existing_count
    assert m["headcount"].iloc[-1] == a.headcount.existing_count + len(a.headcount.plan)


def test_benefits_are_applied():
    a, _, hc, _, _, _ = _run()
    m = hc["monthly"]
    ratio = m["total_comp"] / m["base_comp"]
    expected = 1 + a.headcount.benefits_rate
    assert np.allclose(ratio, expected)


def test_gross_margin_positive_at_scale():
    """At year 5, gross margin should be well into positive territory."""
    _, _, _, _, _, pnl = _run()
    y5 = pnl["annual"][pnl["annual"]["year"] == 2030].iloc[0]
    assert y5["gross_margin"] > 0.5  # healthy SaaS
