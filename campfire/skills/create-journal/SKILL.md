---
name: create-journal
description: Use when the user asks to create a journal entry, post a journal to Campfire, or make debit/credit entries in the general ledger.
---

# Create Journal Entry in Campfire

## API Endpoint

```
POST https://api.meetcampfire.com/coa/api/journal_entry
Authorization: Token {CAMPFIRE_API_KEY}
Content-Type: application/json
```

## Payload Structure

```json
{
  "entity": 20043,
  "type": "journal_entry",
  "date": "2026-03-31",
  "memo": "Monthly depreciation - March 2026",
  "reversal_date": null,
  "transactions": [
    {
      "account": 762243,
      "debit_amount": 500.00,
      "credit_amount": null,
      "bank_description": "Depreciation Expense",
      "department": 62121
    },
    {
      "account": 762247,
      "debit_amount": null,
      "credit_amount": 500.00,
      "bank_description": "Accumulated Depreciation",
      "department": 62121
    }
  ]
}
```

## Field Reference

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| entity | int | Yes | Campfire entity ID (20043=Parent, 20044=West Coast, 20045=Europe) |
| type | string | Yes | Must be "journal_entry" |
| date | string | Yes | YYYY-MM-DD |
| memo | string | Yes | Journal header description |
| reversal_date | string | No | Auto-reversal date. Omit for permanent entries. |
| transactions | array | Yes | Debits must equal credits |

### Transaction Line Fields

| Field | Type | Notes |
|-------|------|-------|
| account | int | Campfire account ID (NOT the GL number) |
| debit_amount | float | Set to null for credit lines |
| credit_amount | float | Set to null for debit lines |
| bank_description | string | Line-level description |
| department | int | 62121=Accounting, 62122=Engineering, 62120=Sales |

## Key Account IDs

| GL # | Campfire ID | Name |
|------|-------------|------|
| 1000 | 762218 | Cash |
| 120000 | 762215 | Accounts Receivable |
| 210000 | 762212 | Accounts Payable |
| 4030 | 762258 | Subscription Revenue |
| 5000 | 762231 | Direct Labor |
| 6100 | 762236 | Rent Expense |
| 6210 | 762240 | Software Subscriptions |
| 6400 | 762242 | Professional Fees |
| 6500 | 762243 | Depreciation Expense |
| 1210 | 762247 | Accumulated Depreciation |

## Before Posting

1. Verify debits = credits
2. Check for duplicates: query existing journals for the same date + memo pattern
3. Confirm entity and account IDs are valid
4. Ask user for confirmation before posting

## Error Handling

| Code | Meaning |
|------|---------|
| 201 | Created (response includes journal ID) |
| 400 | Validation error (check payload) |
| 401 | Bad API token |
