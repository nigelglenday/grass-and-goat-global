---
name: cfo-analysis
description: Use when the user asks a CFO-level question about the business — revenue trends, cash position, burn rate, vendor analysis, budget variance, or any "why did this change" question. Structures the analysis approach and ensures Campfire data is queried before answering.
---

# CFO Analysis

When asked a financial question about the business:

1. **Identify what data you need** — which Campfire MCP tools or API endpoints answer this
2. **Pull the data** — use MCP tools first, fall back to REST API if needed
3. **Analyze** — compute the answer, show your work
4. **Contextualize** — explain what the number means for the business, not just what it is
5. **Flag risks** — if something looks off, say so. Don't bury bad news.

## Question Patterns

**"Why did X change?"** → Pull current and prior period, compute delta, drill into the components that drove it. Show the waterfall: prior period → component changes → current period.

**"What's our runway?"** → Cash balance from balance sheet, monthly burn from trailing 3-month opex average, runway = cash / monthly burn. Flag if under 12 months.

**"Who owes us money?"** → AR aging report, sorted by amount outstanding. Flag anything past 90 days.

**"What's our vendor concentration?"** → Pull all bills by vendor, compute % of total spend per vendor. Flag any vendor over 20% of total.

**"Are we on budget?"** → Pull actuals from Campfire, compare to budget in `budget/configs/`. Compute variance by line item, flag anything over 10% variance.

## Output Format

Lead with the answer, then the supporting data. Tables for numbers. Narrative for context. Don't make the user scroll through raw data to find the insight.
