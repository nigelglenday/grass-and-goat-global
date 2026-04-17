"""Scenario loading — base YAML + optional overrides.

Scenarios are not duplicate files. `base_case.yaml` is the canonical
assumption set; scenario overrides are partial YAMLs that deep-merge onto
the base. This keeps the surface DRY and makes "base ± one change" trivial
to express — the shape v2 sensitivity runners need.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from .assumptions import Assumptions


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict with overrides layered on top of base.

    Nested dicts merge key-by-key. Lists replace wholesale — if the override
    sets `acquisition.cohorts` it replaces the full list. This is usually what
    you want for scenarios (a different acquisition plan, not a partial one).
    """
    result = deepcopy(base)
    for key, val in overrides.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(val, dict)
        ):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = deepcopy(val)
    return result


def load_scenario(
    base_path: str | Path,
    overrides_path: str | Path | None = None,
) -> Assumptions:
    """Load a base YAML and optionally merge an overrides YAML on top."""
    with open(base_path) as f:
        raw = yaml.safe_load(f)

    if overrides_path:
        with open(overrides_path) as f:
            overrides = yaml.safe_load(f) or {}
        raw = _deep_merge(raw, overrides)

    return Assumptions(**raw)
