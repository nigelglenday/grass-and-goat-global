# Campfire Integration

## API Access

- Base URL: `https://api.meetcampfire.com`
- Auth: `Authorization: Token {CAMPFIRE_API_KEY}`
- Key is in `.env` as `CAMPFIRE_API_KEY`

## MCP Tools (12 read-only)

Available via `mcp__campfire__*` when MCP is connected:
1. get_accounts — chart of accounts
2. get_transactions — GL entries with filters
3. get_entities — company entities
4. get_vendors — vendor/customer directory
5. get_departments — department hierarchy
6. get_tags — tags/dimensions
7. income_statement — P&L with cadence options
8. balance_sheet — with cadence options
9. cash_flow_statement — operating/investing/financing
10. get_budgets — budget records
11. get_contracts — revenue recognition contracts
12. get_aging — AP/AR aging analysis

## REST API (beyond MCP)

For write operations or endpoints not covered by MCP. Full reference:
- `../../campfire-llms-full.txt` (182KB) — every endpoint
- `../../campfire-openapi.json` (1.8MB) — full OpenAPI spec

### Key Paths

| Category | Path | Notes |
|----------|------|-------|
| Chart of Accounts | `/coa/api/account` | |
| Journal Entries | `/coa/api/journal_entry` | POST to create |
| Transactions | `/coa/api/transaction/{id}` | |
| Bills | `/coa/api/v1/bill/` | CRUD + pay/void |
| Invoices | `/coa/api/v1/invoice/` | CRUD + pay/void |
| Vendors | `/coa/api/vendor` | |
| Departments | `/coa/api/department` | |
| Entities | `/coa/api/entity` | PATCH to rename |
| Financial Statements | `/ca/api/get_balance_sheet` | |

## Chart of Accounts (48 accounts)

### Revenue
- 4000 Service Revenue
- 4030 Subscription Revenue (child of 4000)

### COGS
- 5000 Direct Labor
- 5010 Subcontractor Costs

### Operating Expenses
- 6100 Rent Expense
- 6110 Utilities Expense
- 6120 Insurance Expense
- 6200 Office Supplies
- 6210 Software Subscriptions
- 6400 Professional Fees
- 6500 Depreciation Expense
- 6600 Travel & Entertainment
- 6700 Miscellaneous Expense

### Balance Sheet
- 1000 Cash (Bank)
- 1010/120000 Accounts Receivable
- 1020 Prepaid Expenses
- 1200 PP&E / 1210 Accumulated Depreciation
- 210000 Accounts Payable
- 2010 Accrued Expenses
- 2020 Deferred Revenue
- 2100 Short-term Loans Payable
- 2200 Long-term Debt
- 3000+ Equity (SAFE Notes, Paid-In Capital, CTA, Treasury Stock)

## Journal Entry Payload

```json
{
  "entity": 20043,
  "type": "journal_entry",
  "date": "2026-03-31",
  "memo": "Description here",
  "transactions": [
    {
      "account": 762236,
      "debit_amount": 1000.00,
      "credit_amount": null,
      "bank_description": "Line description",
      "department": 62121
    },
    {
      "account": 762218,
      "debit_amount": null,
      "credit_amount": 1000.00,
      "bank_description": "Line description",
      "department": 62121
    }
  ]
}
```

IDs must reference Campfire internal IDs (not GL numbers).
Total debits must equal total credits.
