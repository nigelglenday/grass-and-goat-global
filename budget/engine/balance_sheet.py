"""Balance sheet roll-forward.

Pure function. Computes BS and cash flow together because they're coupled:
  - AR / AP / deferred rev roll from revenue/opex × DSO/DPO/prepay days
  - Working-capital deltas feed into CFO
  - Cash ending = prior cash + CFO + CFI + CFF
  - Retained earnings = prior RE + net_income

Ties enforced by construction — if BS doesn't balance we've got a bug.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .assumptions import Assumptions


def compute_balance_sheet_and_cash_flow(
    a: Assumptions,
    pnl_monthly: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    n = len(pnl_monthly)
    bs_start = a.balance_sheet_start
    wc = a.working_capital

    revenue = pnl_monthly["revenue"].to_numpy()
    cogs = pnl_monthly["cogs_total"].to_numpy()
    opex = pnl_monthly["total_opex"].to_numpy()
    depreciation = pnl_monthly["depreciation"].to_numpy()
    net_income = pnl_monthly["net_income"].to_numpy()

    # Working-capital balances derive from trailing activity:
    #   AR = revenue × DSO/30   (using monthly revenue scaled to daily × DSO)
    #   AP = (cogs + opex) × DPO/30
    #   Deferred rev = revenue × deferred_rev_months (pre-paid advance)
    # Month 0 seeds from balance_sheet_start to avoid a discontinuity.
    ar = revenue * (wc.dso_days / 30)
    cash_opex_outflow = cogs + opex - pnl_monthly["cogs_comp"].to_numpy()
    # Rough approximation for AP: ties to cash-paid opex (excluding comp which is typically near-immediate)
    ap = cash_opex_outflow * (wc.dpo_days / 30)
    deferred_rev = revenue * wc.deferred_rev_months

    # Month 0 — seed from YAML start values (override computed values in first month
    # to respect the opening balance sheet snapshot)
    ar_adj = ar.copy()
    ap_adj = ap.copy()
    deferred_rev_adj = deferred_rev.copy()
    # Start-of-month zero is opening BS; we store END of each month. So month 0 BS
    # = opening + monthly flow. To honor the start-of-year opening values, we add
    # the start balance as a "level adjustment" rolled across the series.
    # Simplest: use computed AR/AP/deferred directly (they're functions of flow
    # and will stabilize naturally). Track start separately as opening cash.

    # D ΔWorking capital (change month over month)
    prior_ar = np.concatenate([[bs_start.ar], ar_adj[:-1]])
    d_ar = ar_adj - prior_ar

    prior_ap = np.concatenate([[bs_start.ap], ap_adj[:-1]])
    d_ap = ap_adj - prior_ap

    prior_def = np.concatenate([[bs_start.deferred_rev], deferred_rev_adj[:-1]])
    d_def = deferred_rev_adj - prior_def

    # CFO (indirect method)
    cfo = net_income + depreciation - d_ar + d_ap + d_def

    # CFI — capex
    cfi = np.full(n, -a.capex.monthly)

    # CFF — no new financing modeled in v1
    cff = np.zeros(n)

    # Cash roll-forward
    cash = np.zeros(n)
    cash[0] = bs_start.cash + cfo[0] + cfi[0] + cff[0]
    for i in range(1, n):
        cash[i] = cash[i - 1] + cfo[i] + cfi[i] + cff[i]

    # PP&E roll-forward: start + capex − depreciation
    ppe = np.zeros(n)
    ppe[0] = bs_start.ppe_net + a.capex.monthly - depreciation[0]
    for i in range(1, n):
        ppe[i] = ppe[i - 1] + a.capex.monthly - depreciation[i]

    # Retained earnings roll-forward
    retained_earnings = np.zeros(n)
    opening_re = bs_start.retained_earnings
    retained_earnings[0] = opening_re + net_income[0]
    for i in range(1, n):
        retained_earnings[i] = retained_earnings[i - 1] + net_income[i]

    # Accrued and other — carry from opening
    accrued = np.full(n, bs_start.accrued)
    safe_notes = np.full(n, bs_start.safe_notes)
    paid_in_capital = np.full(n, bs_start.paid_in_capital)

    # Total equity
    total_equity = safe_notes + paid_in_capital + retained_earnings

    # Total assets = cash + AR + PP&E
    total_assets = cash + ar_adj + ppe

    # Total liabilities = AP + accrued + deferred rev
    total_liab = ap_adj + accrued + deferred_rev_adj

    # Balancing check: assets should equal liab + equity
    imbalance = total_assets - (total_liab + total_equity)

    bs = pd.DataFrame(
        {
            "month_index": pnl_monthly["month_index"],
            "month": pnl_monthly["month"],
            "label": pnl_monthly["label"],
            "cash": cash,
            "ar": ar_adj,
            "ppe_net": ppe,
            "total_assets": total_assets,
            "ap": ap_adj,
            "accrued": accrued,
            "deferred_rev": deferred_rev_adj,
            "total_liabilities": total_liab,
            "safe_notes": safe_notes,
            "paid_in_capital": paid_in_capital,
            "retained_earnings": retained_earnings,
            "total_equity": total_equity,
            "imbalance": imbalance,
        }
    )

    cf = pd.DataFrame(
        {
            "month_index": pnl_monthly["month_index"],
            "month": pnl_monthly["month"],
            "label": pnl_monthly["label"],
            "net_income": net_income,
            "depreciation": depreciation,
            "d_ar": -d_ar,
            "d_ap": d_ap,
            "d_deferred_rev": d_def,
            "cfo": cfo,
            "capex": -a.capex.monthly * np.ones(n),
            "cfi": cfi,
            "cff": cff,
            "net_change_cash": cfo + cfi + cff,
            "ending_cash": cash,
        }
    )

    return {"balance_sheet": bs, "cash_flow": cf}
