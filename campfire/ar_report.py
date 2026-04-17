#!/usr/bin/env python3
"""Daily AR update: pull open invoices, bucket by age, compare to yesterday,
narrate with Haiku, write markdown + HTML + snapshot, post to Slack."""

import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import anthropic
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
for p in [ROOT / ".env", ROOT.parent / ".env"]:
    if p.exists():
        load_dotenv(p)
        break

CAMP_KEY = os.environ["CAMPFIRE_API_KEY"]
CAMP = "https://api.meetcampfire.com"
HEADERS = {"Authorization": f"Token {CAMP_KEY}"}

REPORTS_DIR = ROOT / "reports" / "ar"
SNAPSHOTS_DIR = REPORTS_DIR / "snapshots"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

BUCKETS = ["current", "1-30", "31-60", "61-90", "90+"]


def pull_open_invoices():
    out, offset = [], 0
    while True:
        r = requests.get(
            f"{CAMP}/coa/api/v1/invoice/",
            headers=HEADERS,
            params={"limit": 500, "offset": offset, "sort": "-invoice_date"},
        )
        r.raise_for_status()
        data = r.json()
        out.extend(data["results"])
        if len(data["results"]) < 500:
            break
        offset += 500
    return [
        inv for inv in out
        if inv.get("amount_due") and float(inv["amount_due"]) > 0
        and not inv.get("is_deleted")
        and inv.get("status") != "voided"
    ]


def pull_revenue_90d(today):
    start = (today - timedelta(days=90)).isoformat()
    r = requests.get(
        f"{CAMP}/ca/api/get_income_statement",
        headers=HEADERS,
        params={"start_date": start, "end_date": today.isoformat()},
    )
    r.raise_for_status()
    for row in r.json().get("income_statement", []):
        if row.get("account_id") == "REVENUE":
            return float(row.get("Total", 0) or 0)
    return 0.0


def bucket_of(days_past_due):
    if days_past_due is None or days_past_due <= 0:
        return "current"
    if days_past_due <= 30:
        return "1-30"
    if days_past_due <= 60:
        return "31-60"
    if days_past_due <= 90:
        return "61-90"
    return "90+"


def build_snapshot(invoices, revenue_90d, today):
    buckets = {b: {"amount_usd": 0.0, "count": 0} for b in BUCKETS}
    by_currency = {}
    total_ar_usd = 0.0

    for inv in invoices:
        dpd = inv.get("past_due_days") or 0
        b = bucket_of(dpd)
        amt_usd = float(inv.get("amount_due_consolidation") or inv.get("amount_due") or 0)
        buckets[b]["amount_usd"] += amt_usd
        buckets[b]["count"] += 1
        total_ar_usd += amt_usd

        ccy = inv.get("currency", "USD")
        by_currency.setdefault(ccy, {"amount": 0.0, "count": 0})
        by_currency[ccy]["amount"] += float(inv.get("amount_due") or 0)
        by_currency[ccy]["count"] += 1

    dso = (total_ar_usd / (revenue_90d / 90)) if revenue_90d > 0 else None

    overdue = sorted(
        [i for i in invoices if (i.get("past_due_days") or 0) > 0],
        key=lambda i: float(i.get("amount_due_consolidation") or i.get("amount_due") or 0),
        reverse=True,
    )[:10]
    top_overdue = [
        {
            "client": i.get("client_name"),
            "entity": i.get("entity_name"),
            "invoice_number": i.get("invoice_number"),
            "currency": i.get("currency"),
            "amount_due": float(i.get("amount_due") or 0),
            "amount_due_usd": float(i.get("amount_due_consolidation") or i.get("amount_due") or 0),
            "due_date": i.get("due_date"),
            "days_past_due": i.get("past_due_days"),
        }
        for i in overdue
    ]

    return {
        "as_of": today.isoformat(),
        "total_ar_usd": round(total_ar_usd, 2),
        "invoice_count": len(invoices),
        "dso": round(dso, 1) if dso is not None else None,
        "revenue_90d_usd": round(revenue_90d, 2),
        "buckets": {b: {"amount_usd": round(v["amount_usd"], 2), "count": v["count"]}
                    for b, v in buckets.items()},
        "by_currency": {c: {"amount": round(v["amount"], 2), "count": v["count"]}
                        for c, v in by_currency.items()},
        "top_overdue": top_overdue,
    }


def load_prior_snapshot(today):
    prior = sorted(
        f for f in SNAPSHOTS_DIR.glob("*.json")
        if f.stem < today.isoformat()
    )
    if not prior:
        return None
    return json.loads(prior[-1].read_text())


def compute_deltas(today_snap, prior_snap):
    if not prior_snap:
        return None
    def d(a, b):
        if a is None or b is None:
            return None
        return round(a - b, 2)
    return {
        "prior_as_of": prior_snap["as_of"],
        "total_ar_usd": d(today_snap["total_ar_usd"], prior_snap["total_ar_usd"]),
        "dso": d(today_snap["dso"], prior_snap["dso"]),
        "bucket_90plus_usd": d(
            today_snap["buckets"]["90+"]["amount_usd"],
            prior_snap["buckets"]["90+"]["amount_usd"],
        ),
        "count_90plus": today_snap["buckets"]["90+"]["count"] - prior_snap["buckets"]["90+"]["count"],
        "invoice_count": today_snap["invoice_count"] - prior_snap["invoice_count"],
    }


def load_trend(n=14):
    files = sorted(SNAPSHOTS_DIR.glob("*.json"))[-n:]
    return [json.loads(f.read_text()) for f in files]


def format_plain(snap, deltas):
    b = snap["buckets"]
    lines = [
        f"AR SNAPSHOT as of {snap['as_of']}",
        "=" * 50,
        f"  Total AR (USD):       ${snap['total_ar_usd']:>12,.0f}",
        f"  Open invoices:        {snap['invoice_count']:>12}",
        f"  DSO (90d basis):      {snap['dso'] if snap['dso'] is not None else 'n/a':>12}",
        "",
        "AGING BUCKETS (USD)",
        "-" * 50,
    ]
    for bk in BUCKETS:
        lines.append(f"  {bk:<8s}  ${b[bk]['amount_usd']:>12,.0f}  ({b[bk]['count']} inv)")

    if deltas:
        lines += [
            "",
            f"CHANGE vs {deltas['prior_as_of']}",
            "-" * 50,
            f"  Total AR:   {deltas['total_ar_usd']:+,.0f}",
            f"  DSO:        {deltas['dso']:+.1f}" if deltas['dso'] is not None else "  DSO:        n/a",
            f"  90+ USD:    {deltas['bucket_90plus_usd']:+,.0f}",
            f"  90+ count:  {deltas['count_90plus']:+d}",
            f"  Open inv:   {deltas['invoice_count']:+d}",
        ]
    else:
        lines += ["", "(No prior snapshot — trend deltas will appear tomorrow.)"]

    if snap["top_overdue"]:
        lines += ["", "TOP OVERDUE", "-" * 50]
        for o in snap["top_overdue"]:
            lines.append(
                f"  {o['days_past_due']:>4}d  {o['client']:<18s} {o['invoice_number']:<14s} "
                f"${o['amount_due_usd']:>10,.0f}"
            )
    return "\n".join(lines)


def narrate(plain_text):
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=(
            "You are a CFO advisor at a growing B2B subscription company. Be direct. "
            "Focus on what changed, what's at risk, and what to do. Do not audit the "
            "accounting structure. Do not use markdown headers (#). Use bold (**text**) "
            "for emphasis. No preamble."
        ),
        messages=[{
            "role": "user",
            "content": f"""AR snapshot for Grass & Goat Global, Inc. (B2B subscription, enterprise customers):

{plain_text}

Give me exactly 3 bullets:
1. What moved vs. yesterday — or, if no prior day, the shape of the AR book today.
2. Largest at-risk exposure (name names).
3. One collections action for this week.""",
        }],
    )
    return msg.content[0].text


def write_markdown(snap, deltas, narrative, today):
    b = snap["buckets"]
    lines = [
        f"# AR Update — {today.isoformat()}",
        "",
        f"**Total AR:** ${snap['total_ar_usd']:,.0f} USD across {snap['invoice_count']} open invoices  ",
        f"**DSO (90d basis):** {snap['dso'] if snap['dso'] is not None else 'n/a'}",
        "",
        "## Aging",
        "",
        "| Bucket | Amount (USD) | Invoices |",
        "|--------|-------------:|---------:|",
    ]
    for bk in BUCKETS:
        lines.append(f"| {bk} | ${b[bk]['amount_usd']:,.0f} | {b[bk]['count']} |")

    if deltas:
        lines += [
            "",
            f"## Change vs {deltas['prior_as_of']}",
            "",
            f"- Total AR: **{deltas['total_ar_usd']:+,.0f} USD**",
            f"- DSO: **{deltas['dso']:+.1f}**" if deltas['dso'] is not None else "- DSO: n/a",
            f"- 90+ bucket: **{deltas['bucket_90plus_usd']:+,.0f} USD** ({deltas['count_90plus']:+d} invoices)",
            f"- Open invoice count: **{deltas['invoice_count']:+d}**",
        ]

    if len(snap.get("by_currency", {})) > 1:
        lines += ["", "## By Currency", "", "| Currency | Amount | Invoices |", "|---|---:|---:|"]
        for ccy, v in sorted(snap["by_currency"].items()):
            lines.append(f"| {ccy} | {v['amount']:,.0f} | {v['count']} |")

    if snap["top_overdue"]:
        lines += ["", "## Top Overdue", "", "| Days | Client | Invoice | Entity | Amount (USD) |",
                  "|---:|---|---|---|---:|"]
        for o in snap["top_overdue"]:
            lines.append(
                f"| {o['days_past_due']} | {o['client']} | {o['invoice_number']} | "
                f"{o['entity']} | ${o['amount_due_usd']:,.0f} |"
            )

    lines += ["", "## CFO Read", "", narrative, "", "---",
              f"_Generated {datetime.now().isoformat(timespec='seconds')} · "
              f"Campfire → Claude Haiku → GitHub Actions_"]

    out = REPORTS_DIR / f"{today.isoformat()}.md"
    out.write_text("\n".join(lines))
    return out


def write_html(snap, deltas, narrative, today):
    trend = load_trend(14)
    trend_labels = [s["as_of"] for s in trend] + ([today.isoformat()] if not trend or trend[-1]["as_of"] != today.isoformat() else [])
    trend_ar = [s["total_ar_usd"] for s in trend] + ([snap["total_ar_usd"]] if not trend or trend[-1]["as_of"] != today.isoformat() else [])
    trend_dso = [s.get("dso") for s in trend] + ([snap["dso"]] if not trend or trend[-1]["as_of"] != today.isoformat() else [])

    bucket_labels = BUCKETS
    bucket_values = [snap["buckets"][b]["amount_usd"] for b in BUCKETS]

    delta_block = ""
    if deltas:
        delta_block = f"""<div class="deltas">
          <span>Δ AR <b>{deltas['total_ar_usd']:+,.0f}</b></span>
          <span>Δ DSO <b>{(f"{deltas['dso']:+.1f}" if deltas['dso'] is not None else 'n/a')}</b></span>
          <span>Δ 90+ <b>{deltas['bucket_90plus_usd']:+,.0f}</b></span>
          <span class="prior">vs {deltas['prior_as_of']}</span>
        </div>"""

    narrative_html = narrative.replace("**", "__").replace("\n", "<br>")
    narrative_html = re.sub(r"__(.+?)__", r"<strong>\1</strong>", narrative_html)

    rows = "".join(
        f"<tr><td>{o['days_past_due']}d</td><td>{o['client']}</td>"
        f"<td>{o['invoice_number']}</td><td>{o['entity']}</td>"
        f"<td class=num>${o['amount_due_usd']:,.0f}</td></tr>"
        for o in snap["top_overdue"]
    )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>AR Update {today.isoformat()}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  body {{ font-family: -apple-system,BlinkMacSystemFont,sans-serif; max-width: 960px; margin: 40px auto; padding: 0 20px; color: #1c1c1c; }}
  h1 {{ margin-bottom: 4px; }}
  .subtitle {{ color: #888; margin-bottom: 24px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 20px 0; }}
  .kpi {{ background: #f7f7f5; border-radius: 8px; padding: 16px; }}
  .kpi .label {{ color: #666; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; }}
  .kpi .val {{ font-size: 28px; font-weight: 600; margin-top: 4px; }}
  .deltas {{ display: flex; gap: 16px; font-size: 13px; color: #444; margin: 8px 0 24px; }}
  .deltas b {{ color: #000; }}
  .deltas .prior {{ margin-left: auto; color: #999; }}
  .narrative {{ background: #fff8e1; border-left: 3px solid #f6a723; padding: 14px 18px; margin: 20px 0; border-radius: 4px; line-height: 1.5; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin: 24px 0; }}
  .card {{ background: #fff; border: 1px solid #eee; border-radius: 8px; padding: 16px; }}
  .card h3 {{ margin: 0 0 8px; font-size: 14px; color: #555; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #eee; }}
  th {{ color: #666; font-weight: 500; font-size: 12px; text-transform: uppercase; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  footer {{ color: #999; font-size: 12px; margin-top: 32px; }}
</style>
</head><body>
<h1>AR Update</h1>
<div class="subtitle">Grass &amp; Goat Global, Inc. · {today.strftime('%A, %B %-d, %Y')}</div>

<div class="kpis">
  <div class="kpi"><div class="label">Total AR (USD)</div><div class="val">${snap['total_ar_usd']:,.0f}</div></div>
  <div class="kpi"><div class="label">DSO (90d)</div><div class="val">{snap['dso'] if snap['dso'] is not None else 'n/a'}</div></div>
  <div class="kpi"><div class="label">Open Invoices</div><div class="val">{snap['invoice_count']}</div></div>
</div>
{delta_block}

<div class="narrative">{narrative_html}</div>

<div class="charts">
  <div class="card"><h3>Aging Buckets (USD)</h3><canvas id="buckets"></canvas></div>
  <div class="card"><h3>AR Trend (last {max(len(trend_labels),1)} snapshots)</h3><canvas id="trend"></canvas></div>
</div>

<div class="card">
  <h3>Top Overdue</h3>
  <table><thead><tr><th>Days</th><th>Client</th><th>Invoice</th><th>Entity</th><th class=num>Amount (USD)</th></tr></thead>
  <tbody>{rows or '<tr><td colspan=5 style="color:#999;text-align:center;padding:20px">Nothing overdue.</td></tr>'}</tbody></table>
</div>

<footer>Campfire → Claude Haiku → GitHub Actions · generated {datetime.now().isoformat(timespec='seconds')}</footer>

<script>
new Chart(document.getElementById('buckets'), {{
  type: 'bar',
  data: {{ labels: {json.dumps(bucket_labels)},
           datasets: [{{ label: 'USD', data: {json.dumps(bucket_values)},
                        backgroundColor: ['#8bc34a','#ffc107','#ff9800','#ff5722','#c62828'] }}] }},
  options: {{ plugins:{{legend:{{display:false}}}},
              scales:{{y:{{ticks:{{callback: v => '$' + v.toLocaleString()}}}}}} }}
}});
new Chart(document.getElementById('trend'), {{
  type: 'line',
  data: {{ labels: {json.dumps(trend_labels)},
           datasets: [
             {{ label: 'Total AR', data: {json.dumps(trend_ar)}, borderColor:'#1976d2',
                backgroundColor:'rgba(25,118,210,0.08)', fill:true, yAxisID:'y' }},
             {{ label: 'DSO', data: {json.dumps(trend_dso)}, borderColor:'#d81b60',
                borderDash:[4,4], yAxisID:'y1' }}
           ] }},
  options: {{ scales: {{ y: {{ position:'left', ticks:{{callback: v => '$' + v.toLocaleString()}} }},
                        y1: {{ position:'right', grid:{{drawOnChartArea:false}} }} }} }}
}});
</script>
</body></html>"""

    out = REPORTS_DIR / f"{today.isoformat()}.html"
    out.write_text(html)
    return out


def post_slack(snap, deltas, narrative, today):
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        return False

    b = snap["buckets"]
    fields_lines = [
        f"*Total AR*\n${snap['total_ar_usd']:,.0f}",
        f"*DSO*\n{snap['dso'] if snap['dso'] is not None else 'n/a'}",
        f"*Open invoices*\n{snap['invoice_count']}",
        f"*90+ bucket*\n${b['90+']['amount_usd']:,.0f} ({b['90+']['count']})",
    ]
    if deltas:
        delta_bits = [
            f"Δ AR {deltas['total_ar_usd']:+,.0f}",
            f"Δ DSO {deltas['dso']:+.1f}" if deltas['dso'] is not None else "Δ DSO n/a",
            f"Δ 90+ {deltas['bucket_90plus_usd']:+,.0f}",
        ]
        delta_text = " · ".join(delta_bits) + f"   _vs {deltas['prior_as_of']}_"
    else:
        delta_text = "_First snapshot — trend deltas start tomorrow._"

    bucket_rows = "\n".join(
        f"• *{bk}*  ${b[bk]['amount_usd']:,.0f}  ({b[bk]['count']} inv)" for bk in BUCKETS
    )

    narr = narrative.replace("**", "*")

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"Daily AR Update · {today.isoformat()}"}},
        {"type": "section", "fields": [{"type": "mrkdwn", "text": f} for f in fields_lines]},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": delta_text}]},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Aging*\n{bucket_rows}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": narr[:2900]}},
        {"type": "context", "elements": [
            {"type": "mrkdwn", "text": ":fire: Campfire → Claude Haiku → Slack | _automated_"}
        ]},
    ]
    r = requests.post(webhook, json={"blocks": blocks})
    return r.status_code < 300


def main():
    today = date.today()
    print(f"Pulling AR data for {today.isoformat()}...")

    invoices = pull_open_invoices()
    print(f"  open invoices with balance: {len(invoices)}")

    revenue_90d = pull_revenue_90d(today)
    print(f"  trailing 90d revenue: ${revenue_90d:,.0f}")

    snap = build_snapshot(invoices, revenue_90d, today)
    prior = load_prior_snapshot(today)
    deltas = compute_deltas(snap, prior)

    plain = format_plain(snap, deltas)
    print()
    print(plain)
    print("\n--- asking Haiku for a read...\n")

    narrative = narrate(plain)
    print(narrative)

    snap_path = SNAPSHOTS_DIR / f"{today.isoformat()}.json"
    snap_path.write_text(json.dumps(snap, indent=2))
    print(f"\nWrote snapshot: {snap_path.relative_to(ROOT)}")

    md = write_markdown(snap, deltas, narrative, today)
    print(f"Wrote markdown: {md.relative_to(ROOT)}")

    html = write_html(snap, deltas, narrative, today)
    print(f"Wrote HTML:     {html.relative_to(ROOT)}")

    if post_slack(snap, deltas, narrative, today):
        print("Posted to Slack.")
    else:
        print("(No SLACK_WEBHOOK_URL set — skipped Slack post.)")


if __name__ == "__main__":
    main()
