# Grass & Goat Global, Inc.

Demo repo for the Campfire x Claude Code webinar. Shows how a CFO uses Claude Code
with an ERP (Campfire) connected via MCP to query financials, build dashboards,
automate reporting, and translate Excel budget models into Python.

## What's Here

```
campfire/           Campfire API integration — ETL pipelines, dashboards, skills
budget/             FP&A budget model (YAML configs → Python engine → .xlsx)
dashboards/         Generated dashboard outputs
reports/            Generated reports (.xlsx, .docx, .html)
.claude/skills/     Claude Code skills (financial modeling, analysis patterns)
.github/workflows/  GitHub Actions for automated runs
```

## Setup

1. Copy `.env.example` to `.env` and add your Campfire API key
2. Install Claude Code: `npm install -g @anthropic-ai/claude-code`
3. Run `claude` from this directory

The `.mcp.json` connects Claude to your Campfire account automatically.

## The Company

Grass & Goat Global is a subscription goat herd rental company serving
corporate campuses in the Bay Area. Enterprise customers pay monthly for
vegetation management via deployed goat herds.

- Series A venture-backed (SAFE notes, preferred stock)
- 3 entities: Parent (USD), US ops (USD), Europe (EUR)
- ~$170K-200K MRR across 7 enterprise customers
- Departments: Accounting, Engineering, Sales

## Key Patterns

- **Talk to your books** — query Campfire via MCP in natural language
- **Skills as institutional knowledge** — accounting policies, formatting standards
- **YAML configs + Python engines** — budget assumptions separated from logic
- **Self-contained HTML dashboards** — Chart.js, no external dependencies
- **GitHub Actions** — daily automated dashboard generation and Slack delivery
