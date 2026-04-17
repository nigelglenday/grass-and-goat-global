#!/usr/bin/env python3
"""Pull financials from Campfire, summarize with Claude Haiku, print."""

import os, json, requests, anthropic
from dotenv import load_dotenv
from pathlib import Path

# Load .env from repo root or parent
for p in [Path(__file__).resolve().parent.parent / ".env",
          Path(__file__).resolve().parent.parent.parent / ".env"]:
    if p.exists():
        load_dotenv(p)
        break

CAMP_KEY = os.environ["CAMPFIRE_API_KEY"]
CAMP = "https://api.meetcampfire.com"
HEADERS = {"Authorization": f"Token {CAMP_KEY}"}


def pull_income_statement():
    """Fetch quarterly P&L for the last 9 months."""
    r = requests.get(f"{CAMP}/ca/api/get_income_statement", headers=HEADERS,
                     params={"start_date": "2025-07-01", "end_date": "2026-03-31",
                             "cadence": "quarterly"})
    r.raise_for_status()
    return r.json()


def pull_balance_sheet():
    """Fetch latest balance sheet."""
    r = requests.get(f"{CAMP}/ca/api/get_balance_sheet", headers=HEADERS,
                     params={"start_date": "2026-03-01", "end_date": "2026-03-31"})
    r.raise_for_status()
    return r.json()


def format_financials(income, balance):
    """Turn API responses into a structured P&L and balance sheet."""
    # Build lookup — only use summary rows (no parent = top-level subtotal)
    summary = {}
    for r in income.get("income_statement", []):
        atype = r.get("account_type")
        parent = r.get("parent")
        # Summary rows have account_id matching the type name (e.g. "REVENUE")
        if r.get("account_id") == atype:
            summary[atype] = r
    f = lambda key: float(summary.get(key, {}).get("Total", "0"))

    lines = [
        "INCOME STATEMENT (Jul 2025 - Mar 2026)",
        "=" * 45,
        f"  Revenue:              ${f('REVENUE'):>12,.0f}",
        f"  Cost of Goods Sold:   ${f('COGS'):>12,.0f}",
        f"                        {'─' * 12}",
        f"  Gross Profit:         ${f('GROSS_PROFIT'):>12,.0f}",
        f"  Operating Expenses:   ${f('OPERATING_EXPENSES'):>12,.0f}",
        f"                        {'─' * 12}",
        f"  Net Income:           ${f('NET_INCOME'):>12,.0f}",
        "",
        "  Key expense lines:",
    ]

    # Add detail lines — everything with a GL account number
    details = []
    for r in income.get("income_statement", []):
        if r.get("account_number") and r.get("account_type") in ("COGS", "OPERATING_EXPENSES"):
            amt = float(r.get("Total", "0"))
            if amt > 0:
                details.append((r.get("account_name"), amt))
    for name, amt in sorted(details, key=lambda x: -x[1]):
        lines.append(f"    {name:<28s} ${amt:>10,.0f}")

    # Balance sheet
    bs_rows = {r.get("account_name"): r for r in balance.get("balance_sheet", [])}
    def bs(name):
        return float(bs_rows.get(name, {}).get("2026-03-01_Total", "0"))

    lines += [
        "",
        "BALANCE SHEET (as of Mar 2026)",
        "=" * 45,
        f"  Cash:                 ${bs('Cash'):>12,.0f}",
        f"  Accounts Receivable:  ${bs('Accounts Receivable'):>12,.0f}",
        f"  Total Assets:         ${bs('ASSET'):>12,.0f}",
        "",
        f"  Accounts Payable:     ${bs('Accounts Payable'):>12,.0f}",
        f"  Total Liabilities:    ${bs('LIABILITY'):>12,.0f}",
        f"  Total Equity:         ${bs('EQUITY'):>12,.0f}",
    ]

    return "\n".join(lines)


def summarize(text):
    """Send financials to Haiku for a 3-bullet CFO summary."""
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system="You are a CFO advisor at a growing B2B subscription company. Be direct. Focus on business insights, trends, and what needs attention. Do not audit the accounting structure.",
        messages=[{
            "role": "user",
            "content": f"""Here are the latest financials for Grass & Goat Global, Inc.,
a subscription goat herd rental company (B2B, enterprise customers).

{text}

Give me 3 concise bullet points:
1. Revenue and profitability — how are we doing?
2. Cash and collections — any concerns?
3. One thing I should act on this week."""
        }]
    )
    return msg.content[0].text


def main():
    print("Pulling financials from Campfire...")
    income = pull_income_statement()
    balance = pull_balance_sheet()

    text = format_financials(income, balance)
    print(text)
    print("\n---\nAsking Haiku for a summary...\n")

    summary = summarize(text)
    print(summary)

    # Optional: post to Slack
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if webhook:
        requests.post(webhook, json={"text": f"*Weekly CFO Summary*\n{summary}"})
        print("\nPosted to Slack.")


if __name__ == "__main__":
    main()
