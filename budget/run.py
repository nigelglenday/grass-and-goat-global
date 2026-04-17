"""CLI entry point.

Usage:
    python run.py forecast configs/base_case.yaml
    python run.py forecast configs/base_case.yaml --overrides configs/conservative.overrides.yaml
    python run.py forecast configs/base_case.yaml --excel          # also write investor Excel
    python run.py sensitivity configs/base_case.yaml               # v2 — not yet implemented
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from engine.forecast import run_forecast
from engine.scenarios import load_scenario
from output.csv_writer import write_csvs


def cmd_forecast(args: argparse.Namespace) -> int:
    base = Path(args.config)
    overrides = Path(args.overrides) if args.overrides else None
    assumptions = load_scenario(base, overrides)

    t0 = time.time()
    result = run_forecast(assumptions)
    compute_ms = (time.time() - t0) * 1000

    out_dir = Path(args.out_dir) if args.out_dir else Path("out") / assumptions.scenario
    t0 = time.time()
    written = write_csvs(result, out_dir)
    write_ms = (time.time() - t0) * 1000

    print(f"Scenario: {assumptions.scenario}")
    print(f"  Compute:  {compute_ms:6.1f}ms   (hash: {result.id})")
    print(f"  Write:    {write_ms:6.1f}ms   ({len(written)} files)")
    print(f"  Output:   {out_dir}/")
    print()

    # Quick summary
    print("Year-end summary:")
    years = sorted(result.pnl["annual"]["year"].unique())
    print(f"  {'Year':<6}{'ARR':>14}{'Revenue':>14}{'EBITDA':>14}{'GM%':>8}{'Cash':>14}{'Logos':>8}")
    for yr in years:
        arr = result.get("arr", f"{yr}-12")
        rev = result.get("revenue", str(yr))
        ebitda = result.get("ebitda", str(yr))
        ann = result.pnl["annual"]
        gm = ann[ann["year"] == yr]["gross_margin"].iloc[0]
        cash = result.get("cash", f"{yr}-12")
        logos = result.get("logos", f"{yr}-12")
        print(
            f"  {yr:<6}${arr/1e6:>12.1f}M${rev/1e6:>12.1f}M${ebitda/1e6:>12.1f}M"
            f"{gm*100:>6.1f}% ${cash/1e6:>12.1f}M{logos:>7.0f}"
        )

    # Actuals / variance (if enabled in YAML)
    if assumptions.actuals.enabled:
        try:
            from engine.actuals import pull_actuals_and_variance

            env_path = Path(".env")
            variance_df = pull_actuals_and_variance(
                entity_id=assumptions.actuals.entity_id,
                date_from=assumptions.actuals.date_from,
                date_to=assumptions.actuals.date_to,
                forecast_pnl_monthly=result.pnl["monthly"],
                env_file=env_path if env_path.exists() else None,
            )
            variance_df.to_csv(out_dir / "variance.csv", index=False)
            print()
            print(f"  Variance: {out_dir/'variance.csv'}")
            for _, r in variance_df.iterrows():
                print(
                    f"    {r['line_item']:>15}  budget ${r['budget']:>12,.0f}  "
                    f"actual ${r['actual']:>12,.0f}  var ${r['variance']:>12,.0f}"
                )
        except Exception as e:
            print(f"  (Actuals pull failed: {e})")

    if args.excel:
        try:
            from output.excel_writer import write_excel

            xlsx_path = out_dir / "investor_model.xlsx"
            t0 = time.time()
            write_excel(result, xlsx_path)
            xlsx_ms = (time.time() - t0) * 1000
            print()
            print(f"  Excel:    {xlsx_ms:6.1f}ms   {xlsx_path}")
        except ImportError:
            print("  (Excel writer not yet available — skipping --excel)")

    return 0


def cmd_sensitivity(args: argparse.Namespace) -> int:
    print("Sensitivity analysis — v2 (not yet implemented).")
    print()
    print("Planned:")
    print("  tornado:     ±% each parameter, rank by target-metric impact")
    print("  grid:        2-D sweep over (param_x, param_y)")
    print("  monte_carlo: sample from distributions, histogram outputs")
    print()
    print("The engine is already factored for this — the v2 build is additive.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run.py", description="Grass & Goat Global forecast engine"
    )
    sub = p.add_subparsers(dest="command", required=True)

    fp = sub.add_parser("forecast", help="Run a forecast and write CSVs")
    fp.add_argument("config", help="Path to base YAML config")
    fp.add_argument("--overrides", help="Optional overrides YAML to deep-merge")
    fp.add_argument("--out-dir", help="Output directory (default: out/<scenario>/)")
    fp.add_argument("--excel", action="store_true", help="Also write investor Excel")
    fp.set_defaults(func=cmd_forecast)

    sp = sub.add_parser("sensitivity", help="Run sensitivity analysis (v2)")
    sp.add_argument("config", help="Path to base YAML config")
    sp.set_defaults(func=cmd_sensitivity)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
