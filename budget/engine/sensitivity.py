"""Sensitivity analysis — v2.

Not yet implemented. This module exists to anchor the v2 interface so the
engine factoring stays honest. The v1 engine already satisfies the
preconditions:
  - `run_forecast()` is a pure function
  - `Assumptions` is frozen and dotted-path addressable
  - `ForecastResult.get(metric, period)` plucks scalars
  - 60-month runs are well under 100ms (so 1000-run sweeps are seconds, not minutes)

v2 fills in the bodies below without touching anything upstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .assumptions import Assumptions, get_by_path, set_by_path
from .forecast import run_forecast
from .result import ForecastResult


@dataclass
class SensitivityTarget:
    """What output metric to rank/plot against."""
    metric: str
    period: str  # YYYY, YYYY-MM, or YYYY-QN


@dataclass
class TornadoResult:
    """Single-parameter sensitivity output (tornado chart data)."""
    base_value: float
    rows: pd.DataFrame  # columns: param_path, down_value, up_value, down_delta, up_delta


@dataclass
class GridResult:
    """2-D parameter sweep output (heatmap data)."""
    param_x: str
    param_y: str
    values_x: list[float]
    values_y: list[float]
    matrix: pd.DataFrame  # indexed by values_y, columns = values_x


@dataclass
class MonteCarloResult:
    """Monte-Carlo run output (distribution of the target metric)."""
    n_runs: int
    samples: pd.DataFrame  # one row per run: params + target value


def tornado(
    base: Assumptions,
    param_paths: list[str],
    pct_range: float,
    target: SensitivityTarget,
) -> TornadoResult:
    """For each param path, run the forecast at base ± pct_range and record
    the delta in target.metric at target.period. Rank the output by absolute
    impact — classic tornado chart data.

    Args:
        base:        canonical Assumptions
        param_paths: dotted paths to sweep, e.g. ["retention.nrr_annual", ...]
        pct_range:   ±% around the base value (e.g. 0.10 for ±10%)
        target:      (metric, period) to track

    Returns:
        TornadoResult sorted by |max(down_delta, up_delta)| descending.
    """
    raise NotImplementedError("v2: tornado() — implementation pending")


def grid(
    base: Assumptions,
    param_x: str,
    values_x: list[float],
    param_y: str,
    values_y: list[float],
    target: SensitivityTarget,
) -> GridResult:
    """Run the forecast at every (x, y) combination. Returns a matrix of
    target values suitable for a contour/heatmap.
    """
    raise NotImplementedError("v2: grid() — implementation pending")


def monte_carlo(
    base: Assumptions,
    distributions: dict[str, Any],  # path -> Distribution (normal/triangular/uniform)
    n_runs: int,
    target: SensitivityTarget,
    seed: int | None = None,
) -> MonteCarloResult:
    """Sample each path from its distribution, run the forecast, record target.
    Output is a long-format frame for plotting histograms / computing CIs.

    Preconditions (already met in v1):
      - base is frozen; each run uses a fresh model_copy, no shared state
      - run_forecast() caches nothing global; parallel execution is safe
    """
    raise NotImplementedError("v2: monte_carlo() — implementation pending")
