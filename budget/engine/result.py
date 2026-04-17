"""ForecastResult — the addressable output container.

Wraps the pile of DataFrames the engine produces into a single object with:
  - `.id` — deterministic hash of the assumptions, used as a cache key in v2
  - `.get(metric, period)` — pluck a scalar by (metric_name, period_label)

The v2 sensitivity runner leans on `.get()` heavily:
    result.get("ebitda", "2030-12")       -> 46,890,000
    result.get("rule_of_40", "2028-Q4")   -> 157.3
    result.get("arr", "2030")             -> 73,799,540  (year-end)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .assumptions import Assumptions


@dataclass
class ForecastResult:
    assumptions: Assumptions
    revenue: dict[str, pd.DataFrame]
    headcount: dict[str, pd.DataFrame]
    cogs: pd.DataFrame
    opex: pd.DataFrame
    pnl: dict[str, pd.DataFrame]
    balance_sheet: pd.DataFrame
    cash_flow: pd.DataFrame
    saas_metrics: dict[str, pd.DataFrame]
    id: str = field(init=False)

    def __post_init__(self):
        self.id = self._compute_id(self.assumptions)

    @staticmethod
    def _compute_id(a: Assumptions) -> str:
        """Deterministic hash of the assumptions JSON."""
        payload = a.model_dump_json()
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    # --- addressable getter --------------------------------------------------

    # Flow metrics sum across a year; stock metrics take the year-end value.
    FLOW_METRICS = {
        "revenue", "cogs", "gross_profit", "sm", "rnd", "ga", "total_opex",
        "ebitda", "net_income", "depreciation", "new_logos", "new_arr",
        "expansion_arr", "churn_arr", "net_new_arr", "cfo", "cfi", "cff",
    }

    def get(self, metric: str, period: str) -> float:
        """Return a scalar metric at a given period.

        Period can be:
          - "YYYY-MM"   (e.g. "2030-12") — monthly value
          - "YYYY-QN"   (e.g. "2028-Q4") — quarterly value (accepts with or without dash)
          - "YYYY"      (e.g. "2030")    — annual (sum for flows, last for stocks)
        """
        lookups = self._metric_lookups()
        if metric not in lookups:
            raise KeyError(
                f"Unknown metric {metric!r}. Known: {sorted(lookups.keys())[:20]}..."
            )
        df_name, col = lookups[metric]
        df = self._frames()[df_name]

        # Quarterly: "YYYY-QN" or "YYYYQN"
        if "Q" in period:
            period_compact = period.replace("-", "")  # pandas default format
            q_df = self.saas_metrics["quarterly"]
            row = q_df[q_df["quarter"] == period_compact]
            if row.empty:
                raise KeyError(f"Period {period!r} not in quarterly output")
            if col not in row.columns:
                # fall back to monthly and take last of that quarter
                m = self.saas_metrics["monthly"]
                qrows = m[m["quarter"] == period_compact]
                if qrows.empty or col not in qrows.columns:
                    raise KeyError(f"{metric!r} unavailable at quarter {period!r}")
                return float(qrows[col].iloc[-1])
            return float(row[col].iloc[0])

        # Monthly: "YYYY-MM"
        if len(period) == 7 and period[4] == "-":
            year, month = int(period[:4]), int(period[5:])
            mask = (df["month"].dt.year == year) & (df["month"].dt.month == month)
            row = df[mask]
            if row.empty:
                raise KeyError(f"Period {period!r} not in monthly output")
            return float(row[col].iloc[0])

        # Annual: "YYYY"
        if len(period) == 4 and period.isdigit():
            year = int(period)
            # If annual rollup exists and metric is there, prefer it
            annual = self.pnl["annual"]
            if col in annual.columns:
                row = annual[annual["year"] == year]
                if not row.empty:
                    return float(row[col].iloc[0])
            # Otherwise: sum for flows, last for stocks
            mask = df["month"].dt.year == year
            rows = df[mask]
            if rows.empty:
                raise KeyError(f"Year {year} not in output")
            if metric in self.FLOW_METRICS:
                return float(rows[col].sum())
            return float(rows[col].iloc[-1])

        raise ValueError(f"Cannot parse period {period!r}")

    # --- internal wiring -----------------------------------------------------

    def _frames(self) -> dict[str, pd.DataFrame]:
        return {
            "revenue_monthly": self.revenue["monthly"],
            "headcount_monthly": self.headcount["monthly"],
            "pnl_monthly": self.pnl["monthly"],
            "pnl_annual": self.pnl["annual"],
            "balance_sheet": self.balance_sheet,
            "cash_flow": self.cash_flow,
            "saas_monthly": self.saas_metrics["monthly"],
            "saas_quarterly": self.saas_metrics["quarterly"],
        }

    def _metric_lookups(self) -> dict[str, tuple[str, str]]:
        """Map metric name -> (frame_name, column_name)."""
        return {
            # Revenue
            "mrr": ("revenue_monthly", "mrr"),
            "arr": ("revenue_monthly", "arr"),
            "logos": ("revenue_monthly", "logos"),
            "new_logos": ("revenue_monthly", "new_logos"),
            "acv": ("revenue_monthly", "acv"),
            "net_new_arr": ("revenue_monthly", "net_new_arr"),
            # P&L (monthly)
            "revenue": ("pnl_monthly", "revenue"),
            "cogs": ("pnl_monthly", "cogs_total"),
            "gross_profit": ("pnl_monthly", "gross_profit"),
            "gross_margin": ("pnl_monthly", "gross_margin"),
            "sm": ("pnl_monthly", "sm"),
            "rnd": ("pnl_monthly", "rnd"),
            "ga": ("pnl_monthly", "ga"),
            "total_opex": ("pnl_monthly", "total_opex"),
            "ebitda": ("pnl_monthly", "ebitda"),
            "net_income": ("pnl_monthly", "net_income"),
            "operating_margin": ("pnl_monthly", "operating_margin"),
            # BS
            "cash": ("balance_sheet", "cash"),
            "ar": ("balance_sheet", "ar"),
            "total_assets": ("balance_sheet", "total_assets"),
            "total_equity": ("balance_sheet", "total_equity"),
            # CF
            "cfo": ("cash_flow", "cfo"),
            "cfi": ("cash_flow", "cfi"),
            "cff": ("cash_flow", "cff"),
            # SaaS metrics
            "cac": ("saas_monthly", "cac"),
            "ltv": ("saas_monthly", "ltv"),
            "ltv_cac": ("saas_monthly", "ltv_cac"),
            "cac_payback_months": ("saas_monthly", "cac_payback_months"),
            "magic_number": ("saas_monthly", "magic_number"),
            "rule_of_40": ("saas_monthly", "rule_of_40"),
            "burn_multiple": ("saas_monthly", "burn_multiple"),
            "grr_ttm": ("saas_monthly", "grr_ttm"),
            "nrr_ttm": ("saas_monthly", "nrr_ttm"),
            "runway_months": ("saas_monthly", "runway_months"),
            "headcount": ("headcount_monthly", "headcount"),
        }
