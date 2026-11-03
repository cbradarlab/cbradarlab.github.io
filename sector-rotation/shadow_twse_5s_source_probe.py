#!/usr/bin/env python3
"""One-time read-only test of TWSE's public 5-second sector-index report.
Print metadata only. Never save market prices or publish a feed.
"""
import json
import os
import re
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

date = os.environ.get("TRADE_DATE") or "latest"
if date != "latest" and not re.fullmatch(r"20\d{6}", date):
    raise SystemExit("TRADE_DATE must be latest or YYYYMMDD")
base = "https://www.twse.com.tw/exchangeReport/MI_5MINS_INDEX"
url = base + "?" + urlencode({"response": "json", "date": "" if date == "latest" else date})
req = Request(url, headers={
    "User-Agent": "Mozilla/5.0 (compatible; personal-sector-source-probe/0.1)",
    "Accept": "application/json",
    "Origin": "https://cbradarlab.github.io",
})
try:
    with urlopen(req, timeout=25) as resp:
        headers = resp.headers
        body = resp.read(6_000_000)
        status_code = resp.status
except Exception as exc:
    print("SOURCE_HOLD", type(exc).__name__, str(exc)[:250])
    raise SystemExit(2)

print("HTTP", status_code, "CONTENT_TYPE", headers.get("Content-Type"))
print("CORS_ACAO", headers.get("Access-Control-Allow-Origin", "MISSING"))
print("CORS_CREDENTIALS", headers.get("Access-Control-Allow-Credentials", "MISSING"))
try:
    report = json.loads(body)
except (ValueError, UnicodeError) as exc:
    print("SOURCE_HOLD bad JSON:", type(exc).__name__)
    raise SystemExit(2)

fields = report.get("fields", [])
rows = report.get("data", [])
if not fields and isinstance(report.get("tables"), list):
    tables = [x for x in report["tables"] if x.get("fields") and x.get("data")]
    if tables:
        fields, rows = tables[0]["fields"], tables[0]["data"]

times = [str(r[0]).strip() for r in rows if isinstance(r, list) and r]
real_times = [t for t in times if re.fullmatch(r"\d{2}:\d{2}:\d{2}", t)]
minutes = sorted({t[:5] for t in real_times})
print("SOURCE_SUMMARY", json.dumps({
    "date_requested": date, "stat": report.get("stat"),
    "columns": len(fields), "rows": len(rows),
    "time_rows": len(real_times), "unique_minutes": len(minutes),
    "start": real_times[0] if real_times else None,
    "end": real_times[-1] if real_times else None,
    "sector_like_columns": sum("類指數" in str(f) for f in fields),
    "all_rows_same_width": all(len(r) == len(fields) for r in rows if isinstance(r,list)),
}, ensure_ascii=False))
if len(fields) < 20 or len(real_times) < 200 or len(minutes) < 100:
    print("SOURCE_HOLD unexpected schema or incomplete trading day")
    raise SystemExit(2)
print("SOURCE_PASS_TWSE_HISTORY_SCHEMA")
print("NOTE: A successful GET is NOT data redistribution permission or browser CORS permission.")
