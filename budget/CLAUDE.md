# Budget Model

## Pattern

YAML holds assumptions → Python engine calculates → Output renders to .xlsx

```
configs/base_case.yaml    ← all financial assumptions
engine/revenue.py         ← subscription revenue model
engine/headcount.py       ← comp and hiring plan
engine/opex.py            ← non-comp expenses
engine/consolidation.py   ← P&L assembly, actuals vs budget
output/excel.py           ← renders to formatted .xlsx
run.py                    ← CLI entry point
```

## How It Works

1. `run.py` loads a YAML config
2. Engine modules compute each section (revenue, headcount, opex)
3. Consolidation assembles the P&L and pulls actuals from Campfire for variance
4. Output renders to .xlsx following the financial-modeling skill standards

## Creating a New Scenario

Copy a YAML config, change the numbers, run it:
```bash
cp configs/base_case.yaml configs/conservative.yaml
# edit conservative.yaml
python3 run.py configs/conservative.yaml
```

No Python changes needed for new scenarios.

## Pulling Actuals

The model can pull actual results from Campfire to compute budget vs. actual variance.
Set `actuals: true` in the YAML config and provide the date range.
Uses the Campfire MCP or REST API to fetch income statement data.
