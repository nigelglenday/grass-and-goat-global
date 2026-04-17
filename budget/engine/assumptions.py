"""Typed, immutable assumption schema for the forecast engine.

Every YAML key maps to a field here. All models are frozen so mutations
must go through `.model_copy(update={...})` or `set_by_path()` — this is
what lets v2 sensitivity sweeps safely fan out from a base set without
worrying about shared state.

Dotted-path addressability is the v2 contract:
    set_by_path(a, "retention.net_retention_annual", 1.15)
    set_by_path(a, "acquisition.cohorts[3].new_logos", 8)
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ForecastWindow(_Frozen):
    start_month: date  # first-of-month
    periods: int = Field(ge=1, le=240)


class Cohort(_Frozen):
    quarter: str  # e.g. "2026-Q1"
    new_logos: float = Field(ge=0)
    avg_acv: float = Field(ge=0)
    ramp_months: int = Field(ge=0, le=24, default=3)


class Acquisition(_Frozen):
    cohorts: list[Cohort]
    s_and_m_monthly_base: float = Field(ge=0)
    s_and_m_variable_per_logo: float = Field(ge=0)


class Retention(_Frozen):
    gross_retention_annual: float = Field(gt=0, le=1)
    net_retention_annual: float = Field(ge=0)  # can exceed 1 (expansion)


class Pricing(_Frozen):
    acv_escalator_annual: float = 0.0


class COGS(_Frozen):
    direct_labor_pct_revenue: float = Field(ge=0, le=1)
    subcontractor_pct_revenue: float = Field(ge=0, le=1)
    hosting_monthly_base: float = Field(ge=0)


class Hire(_Frozen):
    role: str
    start: date  # month of hire
    salary: float = Field(ge=0)
    dept: str  # "operations" | "engineering" | "sales" | "marketing" | "ga"


class Headcount(_Frozen):
    existing_count: int = Field(ge=0)
    existing_monthly_comp: float = Field(ge=0)
    benefits_rate: float = Field(ge=0, le=1)
    annual_raise: float = 0.0
    plan: list[Hire] = []


class Opex(_Frozen):
    rent_monthly: float = 0.0
    utilities_monthly: float = 0.0
    insurance_monthly: float = 0.0
    office_supplies_monthly: float = 0.0
    software_monthly: float = 0.0
    professional_fees_monthly: float = 0.0
    travel_monthly: float = 0.0
    misc_monthly: float = 0.0
    annual_escalation: float = 0.0


class WorkingCapital(_Frozen):
    dso_days: float = Field(ge=0, default=45)
    dpo_days: float = Field(ge=0, default=30)
    deferred_rev_months: float = Field(ge=0, default=1)


class BalanceSheetStart(_Frozen):
    cash: float = 0.0
    ar: float = 0.0
    ppe_net: float = 0.0
    ap: float = 0.0
    accrued: float = 0.0
    deferred_rev: float = 0.0
    safe_notes: float = 0.0
    paid_in_capital: float = 0.0
    retained_earnings: float = 0.0  # can be negative for pre-rev burn


class Capex(_Frozen):
    monthly: float = 0.0
    depreciation_months: int = Field(ge=1, default=36)


class MetricsConfig(_Frozen):
    ltv_discount_rate_annual: float = 0.10


class ActualsConfig(_Frozen):
    enabled: bool = False
    entity_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None


class Assumptions(_Frozen):
    company: str
    scenario: str = "base_case"
    forecast: ForecastWindow
    acquisition: Acquisition
    retention: Retention
    pricing: Pricing = Pricing()
    cogs: COGS
    headcount: Headcount
    opex: Opex
    working_capital: WorkingCapital = WorkingCapital()
    balance_sheet_start: BalanceSheetStart = BalanceSheetStart()
    capex: Capex = Capex()
    metrics: MetricsConfig = MetricsConfig()
    actuals: ActualsConfig = ActualsConfig()


# --- dotted-path mutation --------------------------------------------------

_PATH_TOKEN = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)(?:\[(\d+)\])?")


def _parse_path(path: str) -> list[tuple[str, int | None]]:
    tokens: list[tuple[str, int | None]] = []
    for part in path.split("."):
        m = _PATH_TOKEN.fullmatch(part)
        if not m:
            raise ValueError(f"Invalid path segment: {part!r}")
        name, idx = m.group(1), m.group(2)
        tokens.append((name, int(idx) if idx is not None else None))
    return tokens


def set_by_path(obj: BaseModel, path: str, value: Any) -> BaseModel:
    """Return a new frozen object with `path` set to `value`.

    Supports dotted paths with list indexing:
        set_by_path(a, "retention.net_retention_annual", 1.15)
        set_by_path(a, "acquisition.cohorts[3].new_logos", 8)
        set_by_path(a, "headcount.plan[0].salary", 100000)

    The original object is unchanged. v2 sensitivity runners rely on this
    to fan out from a base assumption set.
    """
    tokens = _parse_path(path)
    return _set_recursive(obj, tokens, value)


def _set_recursive(node: Any, tokens: list[tuple[str, int | None]], value: Any) -> Any:
    name, idx = tokens[0]
    rest = tokens[1:]

    if not isinstance(node, BaseModel):
        raise TypeError(f"Cannot descend into non-model at {name!r}: {type(node)}")

    current = getattr(node, name)

    if idx is not None:
        if not isinstance(current, list):
            raise TypeError(f"{name!r} is not a list; cannot index [{idx}]")
        new_list = list(current)
        if rest:
            new_list[idx] = _set_recursive(current[idx], rest, value)
        else:
            new_list[idx] = value
        return node.model_copy(update={name: new_list})

    if rest:
        new_child = _set_recursive(current, rest, value)
        return node.model_copy(update={name: new_child})

    return node.model_copy(update={name: value})


def get_by_path(obj: BaseModel, path: str) -> Any:
    """Read a leaf by dotted path. Symmetrical to set_by_path."""
    tokens = _parse_path(path)
    cur: Any = obj
    for name, idx in tokens:
        cur = getattr(cur, name)
        if idx is not None:
            cur = cur[idx]
    return cur
