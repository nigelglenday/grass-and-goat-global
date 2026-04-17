---
name: financial-modeling
description: Investment banking-grade financial modeling standards for Excel output. MANDATORY for any spreadsheet, .xlsx, financial model, budget, forecast, P&L, fund model, pro forma, waterfall, or data analysis output. Enforces the visual grammar and design discipline of bulge-bracket IB models — clean single-sheet layouts, separated inputs from calculations, blue/black color coding, and professional number formatting.
---

# Financial Modeling Standards

> **Technical Implementation:** For openpyxl/pandas code patterns, formula recalculation, and Excel file handling, first read the `xlsx` skill. This skill layers design and formatting standards on top of that technical foundation.

These standards come from the modeling tradition at bulge-bracket investment banks — Morgan Stanley, UBS, Credit Suisse First Boston — where spreadsheets are the primary medium of financial thought. A model isn't just a calculation; it's a communication. The formatting isn't decoration — it's a visual grammar that lets any banker pick up any model and immediately know what's an input, what's a formula, what's linked from elsewhere, and where to look for the drivers.

## Core Philosophy

A clear spreadsheet is an act of compassion toward the reader. A messy one tells them you don't respect their time.

**Every cell is either a hardcode or a formula — never both.** This is the fundamental law. When you see a blue number, you know a human typed it. When you see a black number, you know it's computed. Break this contract and trust in the entire model collapses.

**Never embed a hardcode inside a formula.** `=A1*1.05` is wrong — the 1.05 is a hidden assumption. Pull it out into its own cell, color it blue, label it. Every assumption should be visible, changeable, and auditable in one place.

---

## Layout Principles

### Single Sheet by Default

Strongly prefer one sheet. Organize vertically into logical sections with breathing room (blank rows) between them. The model should flow downward: **Inputs/Drivers → Calculations → Outputs**. The reader scrolls one direction, top to bottom, and the story builds.

Use tabs only when the model genuinely demands separation — e.g., a detailed schedule that would bloat the main flow, a data input table with hundreds of rows, or distinct business units that each need their own P&L before consolidation. When you do use tabs, every cross-tab reference gets **green text** so the reader knows they need to look elsewhere.

### The Elevator Shaft

The leftmost column should be **narrow and completely empty** — no content, no formatting, no borders, no shading. This is the elevator shaft. It gives the eye a vertical anchor while scrolling through a long model. Your labels start in the next column over.

This is the only column that should be artificially narrow. Leave all other columns at normal width — don't compress anything to "fit on screen."

### The Input Column

Designate one column as the home for all driver assumptions. Every hardcoded assumption lives here, in blue, on the same row as the line item it drives. The time-series columns to its right contain formulas that reference back to this input column.

This creates a single vertical stripe of blue numbers that a reviewer can scan to understand every assumption in the model at a glance. It's far superior to scattering assumptions across a separate tab where they disconnect from the line items they affect.

### Standard Flow (Left to Right)

The general column progression:

```
Elevator shaft | Row labels | Annotations | Input column | Time series →
```

- **Row labels**: Clear, concise names for each line item
- **Annotations**: Units, frequency, or context notes (in red text) — e.g., "annual", "% of AUM", "per unit". Keep these out of the label itself so labels stay clean
- **Input column**: Blue hardcoded assumptions/drivers
- **Time series**: Periods flowing left to right (months, quarters, years)

The exact column letters will vary by model. What matters is the pattern: labels on the left, a single input column, then the time series. Don't force every model into identical column assignments — adapt the layout to what the model needs while preserving this flow.

---

## Header & Title Area

- **Row 1**: Model title with a thin bottom border extending to the rightmost column
- **Row 2**: Units declaration — "$mm, unless noted" or "$000s, unless noted" — stated once, not repeated on every row
- **Row 3+**: Content begins

The units note eliminates redundancy. You don't need "($ millions)" on every revenue line when the header already told you.

---

## Period/Date Columns

**Dates are numbers, not text.** Use actual date values with number formatting to control display.

- **Monthly**: First period is a hardcoded end-of-month date (blue). Subsequent periods use `=EOMONTH(prior, 1)` (black). Format as `mmm-yy` to display "Jan-24".
- **Annual**: First period is a hardcoded year-end date (blue). Subsequent use `=EOMONTH(prior, 12)`. Format as `yyyy` to display "2024".
- **Period numbers**: First period is a hardcoded `1` (blue). Subsequent use `=prior+1`. Apply custom format `"Month" 0` or `"Year" 0` — never use text strings for period labels.

**Aggregation column**: If you have monthly periods for a year, add a total column at the end. Use a date value formatted as `yyyy` (e.g., displays "2024"). Bold it with a light background to visually separate it from the period columns.

**Optional row above dates**: Can label data type — "Actual", "Budget", "Pro Forma" — helpful when mixing historical and projected data.

---

## Color Coding

This is non-negotiable. It's the visual contract that makes models readable across teams, firms, and years.

| Color | Meaning | RGB |
|-------|---------|-----|
| **Blue text** | Hardcoded input — a number a human typed and might change | 0, 0, 255 |
| **Black text** | Formula — computed, don't touch | 0, 0, 0 |
| **Green text** | Linked from another tab | 0, 128, 0 |
| **Orange text** | Pulled from an external source or file | 255, 165, 0 |
| **Red text** | Annotations, notes, flags, warnings | 255, 0, 0 |
| **Yellow background** | Placeholder or key assumption needing attention | 255, 242, 204 |

**Section headers** (e.g., "REVENUE", "EXPENSES", "P&L") use **dark blue background with white bold text**. The shading extends across all columns to the rightmost column of the model — not just the label cell. This creates clean visual bands that segment the model.

---

## Number Formatting

### The Three Rules

1. **Negatives in parentheses**, not minus signs → `(1,000)` not `-1,000`
2. **Zeros as dashes** → `-` not `0`
3. **Always use commas** → `1,000,000` not `1000000`

### Format Strings

```
Currency:     $#,##0;($#,##0);"-"
Percentage:   0.0%;(0.0%);"-"
General:      #,##0;(#,##0);"-"
Multiple:     0.0x
```

### Decimal Discipline

- Dollar amounts: 0 decimals for large numbers, up to 2 for precision
- Growth rates/percentages: 1 decimal (15.2%)
- Interest rates/yields: up to 2 decimals
- Rarely need more than 4 significant digits total

### Alignment

- **Numbers**: right-aligned, always
- **Text**: left-aligned
- **Column headers**: centered is acceptable

---

## Formula Patterns

### Referencing the Input Column

The time-series formula references the input column with a locked column reference, and a period-specific row reference for anything that varies by period:

```
Input column:    rate = 0.0008     (blue, hardcoded)
Period column:   =$input*H$9/12   (black, formula — column locked on input, row locked on reference)
```

Use mixed references deliberately — lock what shouldn't move when copying.

### Horizontal Propagation

**Pattern 1: Period-dependent formula** — repeats the same structure, pulling different period data:
```
H: =$input*H$base/12
I: =$input*I$base/12
```

**Pattern 2: Steady-state carry-forward** — first period references the input column, subsequent periods reference the prior period:
```
H: =input/12          (first period)
I: =H35               (carries forward)
```

Use Pattern 2 only when the value genuinely doesn't change period to period. Use Pattern 1 when the calculation depends on period-varying data.

### Rolling Balances

```
Beginning: 0                          (blue, hardcoded)
Period 1:  =period_flow + beginning   (running balance)
Period 2:  =period_flow + prior       (continues rolling)
```

### Subtotals

- Indent subtotal labels with leading spaces: `"     Total Direct Expenses"`
- **Bold all totals and subtotals** — both label and values
- **Thin top border above totals** when summing rows directly above (the border "closes" the group)
  - Border spans only the number columns, not the label columns
  - If there's already a blank row or section break above, skip the border — it's redundant
- Use `SUM()` for subtotals, never manual addition of individual cells

---

## Section Organization

A typical model flows top to bottom in this order:

```
TITLE + UNITS

OPERATING ASSUMPTIONS
  Capital/AUM build, volume drivers, rate assumptions

REVENUE
  Revenue lines → Total Revenue

EXPENSES
  Variable/direct → Fixed → Allocated → Total Expenses

P&L / OUTPUT
  Revenue less Expenses → Net Income → Derived metrics
```

Blank rows between sections create breathing room. The reader should be able to glance at the left column and understand the model's architecture without reading a single number.

### Section Headers

- **Major sections**: Dark blue background, white bold text, full-width shading
- **Subsections**: Bold + underline, no background — groups related rows within a section

---

## Visual Design

### Gridlines Off

Turn them off. Use borders intentionally and sparingly — a thin border under the title row (full width), thin borders at section boundaries. **No double-line borders** — they look dated. Single thin lines only.

### Merged Cells

Never. They break copy-paste, formula references, sorting, filtering — everything. There is no situation where merged cells are the right choice in a working model.

### Row Shading

Alternating shading can help readability in dense data tables. Use it sparingly and with very subtle colors — the model should not look like a candy cane.

---

## Anti-Patterns

1. **Multiple sheets when one will do** — resist the urge to "organize" into tabs
2. **Hardcodes embedded in formulas** — `=A1*1.05` hides an assumption
3. **Merged cells** — breaks everything
4. **Assumptions on a separate sheet** — disconnects drivers from their line items
5. **Minus signs for negatives** — use parentheses
6. **Zeros displayed as 0** — use dashes
7. **Missing commas** — `1000000` is hostile to the reader
8. **Excessive decimals** — false precision is noise
9. **Scattered inputs** — blue numbers should form one clean vertical stripe
10. **Short section shading** — blue header bars and title borders extend to the rightmost column
11. **Unbolded totals** — every total and subtotal must be bold
12. **Vague file names** — "Fund Model v3" beats "Nigel's numbers.xlsx"
13. **Units on every row** — state it once at the top

---

## Before Delivery

Does this model pass the "stranger test"? Could someone who has never seen it before sit down and understand:
- What's an input vs. what's calculated? (blue/black)
- Where all the assumptions live? (input column)
- What the model is computing and why? (section flow, labels)
- What to change to run a different scenario? (blue cells in the input column)

If yes, ship it. If not, keep refining.
