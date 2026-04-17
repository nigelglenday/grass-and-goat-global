"""Forecast orchestrator.

Pure function. This is the single entry point v2 sensitivity runners use:
    result = run_forecast(assumptions)

No file I/O. No prints. No MCP calls. Everything above is concerned with
running the math and nothing else. CSV writing, Excel writing, Campfire
pulls all live at the edges.
"""

from __future__ import annotations

from .assumptions import Assumptions
from .balance_sheet import compute_balance_sheet_and_cash_flow
from .cogs import compute_cogs
from .headcount import compute_headcount
from .opex import compute_opex
from .pnl import compute_pnl
from .result import ForecastResult
from .revenue import compute_revenue
from .saas_metrics import compute_saas_metrics


def run_forecast(assumptions: Assumptions) -> ForecastResult:
    rev = compute_revenue(assumptions)
    hc = compute_headcount(assumptions)
    cogs = compute_cogs(assumptions, rev["monthly"], hc["monthly"])
    op = compute_opex(assumptions, rev["monthly"])
    pnl = compute_pnl(assumptions, rev["monthly"], cogs, op, hc["monthly"])
    bscf = compute_balance_sheet_and_cash_flow(assumptions, pnl["monthly"])
    metrics = compute_saas_metrics(
        assumptions,
        rev["monthly"],
        pnl["monthly"],
        bscf["cash_flow"],
        bscf["balance_sheet"],
    )
    return ForecastResult(
        assumptions=assumptions,
        revenue=rev,
        headcount=hc,
        cogs=cogs,
        opex=op,
        pnl=pnl,
        balance_sheet=bscf["balance_sheet"],
        cash_flow=bscf["cash_flow"],
        saas_metrics=metrics,
    )
