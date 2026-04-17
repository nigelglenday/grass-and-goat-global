"""Campfire actuals integration — budget vs actual variance.

Edge-layer I/O. Called from `run.py` (not from within `run_forecast`) so the
engine stays pure. Uses Campfire's REST API to pull income statement and
balance sheet, then produces a variance frame against the forecast output.

Auth: `Authorization: Token <CAMPFIRE_API_KEY>` from .env.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests


CAMPFIRE_BASE = "https://api.meetcampfire.com"


class CampfireClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("CAMPFIRE_API_KEY")
        if not self.token:
            raise RuntimeError(
                "CAMPFIRE_API_KEY not set. Export it or load .env before calling."
            )
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Token {self.token}", "Content-Type": "application/json"}
        )

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{CAMPFIRE_BASE}{path}"
        r = self.session.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def income_statement(
        self, entity_id: int, date_from: date, date_to: date
    ) -> pd.DataFrame:
        data = self.get(
            "/ca/api/get_cash_basis_income_statement",
            params={
                "entity_id": entity_id,
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
            },
        )
        return _flatten_statement(data)

    def balance_sheet(
        self, entity_id: int, as_of: date
    ) -> pd.DataFrame:
        data = self.get(
            "/ca/api/get_balance_sheet",
            params={
                "entity_id": entity_id,
                "as_of_date": as_of.isoformat(),
            },
        )
        return _flatten_statement(data)


def _flatten_statement(data: Any) -> pd.DataFrame:
    """Best-effort flatten of Campfire's nested statement payload to a
    long-format DataFrame: account, account_type, amount.

    The REST response shape varies; this is a pragmatic adapter that works
    with the current demo-company layout. If Campfire changes the shape,
    update here — the rest of the engine is insulated.
    """
    rows: list[dict[str, Any]] = []

    def walk(node: Any, path: list[str]):
        if isinstance(node, dict):
            # Leaf: has 'amount' or 'balance'
            if "amount" in node or "balance" in node:
                rows.append(
                    {
                        "account": node.get("name") or node.get("account_name") or ".".join(path),
                        "account_type": node.get("type") or (path[0] if path else ""),
                        "amount": float(node.get("amount") or node.get("balance") or 0),
                    }
                )
                return
            for k, v in node.items():
                walk(v, path + [str(k)])
        elif isinstance(node, list):
            for item in node:
                walk(item, path)

    walk(data, [])
    return pd.DataFrame(rows)


def compute_variance(
    forecast_pnl_monthly: pd.DataFrame,
    actuals: pd.DataFrame,
    date_from: date,
    date_to: date,
) -> pd.DataFrame:
    """Compare forecast vs Campfire actuals for the YTD window.

    For v1 we aggregate both sides to a single period (date_from..date_to)
    and diff the totals. Monthly-level variance requires monthly Campfire
    cadence which we can add when needed.
    """
    # Forecast totals for the window
    fx = forecast_pnl_monthly.copy()
    fx["month"] = pd.to_datetime(fx["month"])
    mask = (fx["month"] >= pd.Timestamp(date_from)) & (
        fx["month"] <= pd.Timestamp(date_to)
    )
    f_window = fx[mask]

    forecast_totals = {
        "revenue": f_window["revenue"].sum(),
        "cogs_total": f_window["cogs_total"].sum(),
        "gross_profit": f_window["gross_profit"].sum(),
        "total_opex": f_window["total_opex"].sum(),
        "ebitda": f_window["ebitda"].sum(),
        "net_income": f_window["net_income"].sum(),
    }

    # Actuals — best-effort map from Campfire account types
    actual_totals = {
        k: 0.0
        for k in forecast_totals
    }
    if not actuals.empty:
        # Very rough mapping. Refine when we see the real payload.
        for _, r in actuals.iterrows():
            t = str(r.get("account_type", "")).lower()
            amt = r["amount"]
            if "revenue" in t or "income" in t:
                actual_totals["revenue"] += amt
            elif "cogs" in t or "cost_of_goods" in t:
                actual_totals["cogs_total"] += amt
            elif "expense" in t or "opex" in t:
                actual_totals["total_opex"] += amt

        actual_totals["gross_profit"] = (
            actual_totals["revenue"] - actual_totals["cogs_total"]
        )
        actual_totals["ebitda"] = (
            actual_totals["gross_profit"] - actual_totals["total_opex"]
        )
        actual_totals["net_income"] = actual_totals["ebitda"]

    rows = []
    for key in forecast_totals:
        budget = forecast_totals[key]
        actual = actual_totals[key]
        rows.append(
            {
                "line_item": key,
                "budget": budget,
                "actual": actual,
                "variance": actual - budget,
                "variance_pct": (actual - budget) / budget if budget else 0.0,
            }
        )
    return pd.DataFrame(rows)


def pull_actuals_and_variance(
    entity_id: int,
    date_from: date,
    date_to: date,
    forecast_pnl_monthly: pd.DataFrame,
    env_file: str | Path | None = None,
) -> pd.DataFrame:
    """Convenience wrapper. Loads env (optional), pulls actuals, returns variance."""
    if env_file:
        _load_env(env_file)

    client = CampfireClient()
    is_actuals = client.income_statement(entity_id, date_from, date_to)
    return compute_variance(forecast_pnl_monthly, is_actuals, date_from, date_to)


def _load_env(env_file: str | Path) -> None:
    """Minimal .env loader — avoids python-dotenv dependency."""
    p = Path(env_file)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
