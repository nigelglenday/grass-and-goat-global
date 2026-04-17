"""Write a ForecastResult to a directory of CSVs.

Edge-layer I/O. The engine doesn't know this file exists.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from engine.result import ForecastResult


def write_csvs(result: ForecastResult, out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    files: dict[str, pd.DataFrame] = {
        "revenue_cohorts.csv": result.revenue["cohort_matrix"].reset_index(),
        "revenue_cohort_logos.csv": result.revenue["cohort_logos"].reset_index(),
        "revenue_summary.csv": result.revenue["monthly"],
        "pnl_monthly.csv": result.pnl["monthly"],
        "pnl_annual.csv": result.pnl["annual"],
        "headcount.csv": result.headcount["monthly"],
        "headcount_roster.csv": result.headcount["roster"],
        "cogs.csv": result.cogs,
        "opex.csv": result.opex,
        "balance_sheet.csv": result.balance_sheet,
        "cash_flow.csv": result.cash_flow,
        "saas_metrics_monthly.csv": result.saas_metrics["monthly"],
        "saas_metrics_quarterly.csv": result.saas_metrics["quarterly"],
    }

    written: list[Path] = []
    for name, df in files.items():
        path = out / name
        df.to_csv(path, index=False)
        written.append(path)
    return written
