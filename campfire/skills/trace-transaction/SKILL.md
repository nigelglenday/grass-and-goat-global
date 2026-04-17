---
name: trace-transaction
description: Use when the user asks to trace a transaction, find a journal entry, look up a specific GL entry, or understand where a number came from in Campfire.
---

# Trace Transaction

Trace a transaction through Campfire's data model to understand where a number
came from and how it flows through the books.

## Data Model

```
Journal Entry (header)
  ├── memo, date, entity, order #
  └── transactions[] (line items)
       ├── account (GL account)
       ├── debit_amount / credit_amount
       ├── vendor, department, tags
       └── bank_description
```

## Tracing Patterns

### From a P&L line to the transactions behind it

1. Identify the account (e.g., "Software Subscriptions" = account 762240)
2. Pull transactions: `get_transactions(account_id=762240, date_from=..., date_to=...)`
3. Group by vendor to see who drove the spend
4. Drill into specific journal entries if needed

### From a vendor to their impact

1. Find the vendor ID: `get_vendors(q="Amazon")`
2. Pull their transactions: `get_transactions(vendor_id=...)`
3. Summarize by account to see where they hit the P&L
4. Pull their bills: `get_bills(vendor_id=...)`

### From a balance sheet line to its components

1. Identify the account (e.g., AR = 762215)
2. Pull transactions for the period
3. Reconcile: opening balance + debits - credits = closing balance
4. For AR: cross-reference with `get_invoices()` to see customer detail

## API Endpoints

| What | Endpoint |
|------|----------|
| GL transactions | `GET /coa/api/transaction?account_id=X&date_from=Y&date_to=Z` |
| Journal entry | `GET /coa/api/journal_entry/{id}` |
| Bills by vendor | `GET /coa/api/v1/bill/?vendor_id=X` |
| Invoices by client | `GET /coa/api/v1/invoice/?client_id=X` |

Or use MCP: `get_transactions(account_id=..., vendor_id=..., date_from=..., date_to=...)`
