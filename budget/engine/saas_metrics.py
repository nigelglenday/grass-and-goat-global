"""SaaS metrics — the investor view.

Pure function. Computes monthly and quarterly versions of every metric a
Series B/C investor asks about. All trailing-window metrics use explicit
lookback so "CAC" at month 12 means the S&M spent in months 10-12 divided
by the logos landed in those same months.

Metrics:
  Revenue: MRR, ARR, Net New ARR, New ARR, Expansion ARR, Churn ARR
  Retention: GRR (annual, trailing 12mo), NRR (annual, trailing 12mo)
  Customers: total logos, ACV
  Unit econ: CAC, LTV, LTV/CAC, CAC payback (months)
  Efficiency: Magic Number, Rule of 40, Burn Multiple
  Liquidity: Cash, Monthly Burn, Runway (months)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .assumptions import Assumptions


def _trailing_sum(series: np.ndarray, window: int) -> np.ndarray:
    """Trailing sum with partial windows at the start."""
    return (
        pd.Series(series).rolling(window=window, min_periods=1).sum().to_numpy()
    )


def _trailing_mean(series: np.ndarray, window: int) -> np.ndarray:
    return (
        pd.Series(series).rolling(window=window, min_periods=1).mean().to_numpy()
    )


def compute_saas_metrics(
    a: Assumptions,
    revenue_monthly: pd.DataFrame,
    pnl_monthly: pd.DataFrame,
    cash_flow: pd.DataFrame,
    bs: pd.DataFrame,
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

    # Revenue-side metrics
    m["mrr"] = revenue_monthly["mrr"].to_numpy()
    m["arr"] = revenue_monthly["arr"].to_numpy()
    m["new_logos"] = revenue_monthly["new_logos"].to_numpy()
    m["total_logos"] = revenue_monthly["logos"].to_numpy()
    m["acv"] = revenue_monthly["acv"].to_numpy()
    m["new_arr"] = revenue_monthly["new_mrr"].to_numpy() * 12
    m["expansion_arr"] = revenue_monthly["expansion_mrr"].to_numpy() * 12
    m["churn_arr"] = revenue_monthly["churn_mrr"].to_numpy() * 12
    m["net_new_arr"] = revenue_monthly["net_new_arr"].to_numpy()

    # Trailing 12-month GRR/NRR (effective realized rates)
    # GRR realized = (MRR_now - expansion trailing - new trailing) / MRR_12mo_ago
    trailing_new = _trailing_sum(revenue_monthly["new_mrr"].to_numpy(), 12)
    trailing_expansion = _trailing_sum(
        revenue_monthly["expansion_mrr"].to_numpy(), 12
    )
    mrr = m["mrr"].to_numpy()
    mrr_12_ago = np.concatenate([np.full(12, np.nan), mrr[:-12]])
    retained_base = mrr - trailing_new - trailing_expansion
    m["grr_ttm"] = np.where(
        mrr_12_ago > 0,
        retained_base / mrr_12_ago,
        np.nan,
    )
    m["nrr_ttm"] = np.where(
        mrr_12_ago > 0,
        (mrr - trailing_new) / mrr_12_ago,
        np.nan,
    )

    # Unit economics
    sm_monthly = pnl_monthly["sm"].to_numpy()
    new_logos = m["new_logos"].to_numpy()

    # CAC — trailing 3-month S&M / trailing 3-month new logos
    ttm3_sm = _trailing_sum(sm_monthly, 3)
    ttm3_logos = _trailing_sum(new_logos, 3)
    m["cac"] = np.where(ttm3_logos > 0, ttm3_sm / ttm3_logos, np.nan)

    # ARPU (monthly) per logo
    total_logos = m["total_logos"].to_numpy()
    m["arpu_monthly"] = np.where(total_logos > 0, mrr / total_logos, 0.0)
    gross_margin = pnl_monthly["gross_margin"].to_numpy()
    m["gross_margin"] = gross_margin

    # LTV = ARPU_monthly × gross_margin / (monthly_churn + monthly_discount)
    monthly_churn = 1 - (a.retention.gross_retention_annual ** (1 / 12))
    monthly_discount = a.metrics.ltv_discount_rate_annual / 12
    m["ltv"] = np.where(
        (monthly_churn + monthly_discount) > 0,
        m["arpu_monthly"] * gross_margin / (monthly_churn + monthly_discount),
        np.nan,
    )
    m["ltv_cac"] = np.where(m["cac"] > 0, m["ltv"] / m["cac"], np.nan)

    # CAC Payback (months) = CAC / (ARPU × gross_margin)
    denom = m["arpu_monthly"] * gross_margin
    m["cac_payback_months"] = np.where(denom > 0, m["cac"] / denom, np.nan)

    # Magic Number: ((current Q ARR - prior Q ARR) × 4) / prior Q S&M
    # Compute at quarter boundaries then broadcast
    q_arr = revenue_monthly.groupby("quarter")["arr"].last()
    q_sm = pd.Series(sm_monthly, index=revenue_monthly["quarter"].to_numpy()).groupby(
        level=0
    ).sum()
    q_magic = (q_arr.diff() * 4 / q_sm.shift(1)).rename("magic_number")
    m["magic_number"] = m["quarter"].map(q_magic)

    # Rule of 40: YoY ARR growth% + op margin%
    arr_12_ago = np.concatenate([np.full(12, np.nan), m["arr"].to_numpy()[:-12]])
    m["arr_yoy_growth"] = np.where(
        (arr_12_ago > 0) & ~np.isnan(arr_12_ago),
        (m["arr"] - arr_12_ago) / arr_12_ago,
        np.nan,
    )
    # Op margin on trailing-12 EBITDA / revenue
    ttm_ebitda = _trailing_sum(pnl_monthly["ebitda"].to_numpy(), 12)
    ttm_revenue = _trailing_sum(pnl_monthly["revenue"].to_numpy(), 12)
    m["op_margin_ttm"] = np.where(ttm_revenue > 0, ttm_ebitda / ttm_revenue, np.nan)
    m["rule_of_40"] = (m["arr_yoy_growth"] + m["op_margin_ttm"]) * 100

    # Burn Multiple = net burn / Net New ARR (quarterly)
    q_cfo = pd.Series(cash_flow["cfo"].to_numpy(), index=revenue_monthly["quarter"].to_numpy()).groupby(level=0).sum()
    q_net_new_arr = revenue_monthly.groupby("quarter")["net_new_arr"].sum() / 12  # net new ARR during Q
    # Use the ARR at end of Q minus ARR at end of prior Q
    q_end_arr = revenue_monthly.groupby("quarter")["arr"].last()
    q_net_new_arr = q_end_arr.diff()
    q_net_burn = -q_cfo  # positive burn = negative CFO
    q_burn_multiple = np.where(
        q_net_new_arr > 0, q_net_burn / q_net_new_arr, np.nan
    )
    q_burn_multiple_series = pd.Series(q_burn_multiple, index=q_end_arr.index)
    m["burn_multiple"] = m["quarter"].map(q_burn_multiple_series)

    # Cash & Runway
    m["cash"] = bs["cash"].to_numpy()
    # Monthly burn = trailing 3mo avg of -CFO (positive = burn)
    m["monthly_burn"] = _trailing_mean(-cash_flow["cfo"].to_numpy(), 3)
    m["runway_months"] = np.where(
        m["monthly_burn"] > 0,
        m["cash"] / m["monthly_burn"],
        np.inf,  # profitable — infinite runway
    )

    # Quarterly rollup
    quarterly = (
        m.groupby("quarter")
        .agg(
            arr=("arr", "last"),
            mrr=("mrr", "last"),
            new_logos=("new_logos", "sum"),
            total_logos=("total_logos", "last"),
            acv=("acv", "last"),
            new_arr=("new_arr", "sum"),
            expansion_arr=("expansion_arr", "sum"),
            churn_arr=("churn_arr", "sum"),
            net_new_arr=("net_new_arr", "sum"),
            cac=("cac", "last"),
            ltv=("ltv", "last"),
            ltv_cac=("ltv_cac", "last"),
            cac_payback_months=("cac_payback_months", "last"),
            magic_number=("magic_number", "last"),
            rule_of_40=("rule_of_40", "last"),
            burn_multiple=("burn_multiple", "last"),
            grr_ttm=("grr_ttm", "last"),
            nrr_ttm=("nrr_ttm", "last"),
            cash=("cash", "last"),
            runway_months=("runway_months", "last"),
        )
        .reset_index()
    )

    return {"monthly": m, "quarterly": quarterly}
