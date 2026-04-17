# Grass & Goat Global, Inc.

Subscription goat herd rental for corporate campus vegetation management.
Bay Area tech companies as customers. Series A venture-backed.

## Company Structure

| Entity | Campfire ID | Currency | Role |
|--------|-------------|----------|------|
| Grass & Goat Global, Inc. | 20043 | USD | Parent / Holding Co |
| G&G West Coast Ops | 20044 | USD | US Operating Subsidiary |
| G&G Europe | 20045 | EUR | International Subsidiary |

## Departments
- Accounting (62121)
- Engineering (62122)
- Sales (62120)

## Campfire API

Base URL: `https://api.meetcampfire.com`
Auth: `Authorization: Token <CAMPFIRE_API_KEY>` (NOT Bearer)
API key in `.env`

Key paths: see `campfire/CLAUDE.md` for full reference.

## Repo Structure

```
campfire/          ← Campfire API integrations, ETL pipelines, dashboards
budget/            ← FP&A budget model (yaml configs → Python engine → .xlsx)
dashboards/        ← Generated dashboard outputs
reports/           ← Generated reports (.xlsx, .docx, .html)
.claude/skills/    ← Claude Code skills (formatting, analysis patterns)
.github/workflows/ ← Automated runs (daily dashboards, weekly summaries)
```

## Key Patterns

- **YAML holds assumptions, Python holds logic.** Financial assumptions live in
  `budget/configs/*.yaml`, never hardcoded in Python.
- **Skills enforce standards.** The `financial-modeling` skill ensures every .xlsx
  output follows IB-grade formatting. The `cfo-analysis` skill structures how
  Claude approaches financial questions.
- **Dashboards are self-contained HTML.** Chart.js inlined, no external dependencies.
  ETL scripts pull from Campfire API and render the HTML template.
- **Reports land in `reports/`.** This folder syncs to Google Drive for sharing.
