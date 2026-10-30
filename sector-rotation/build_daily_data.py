#!/usr/bin/env python3
"""Convert a Shioaji minute OHLCV CSV into a validated, static daily snapshot.
No credentials, external dependencies, or network access required.
Usage: python sector-rotation/build_daily_data.py input.csv sector-rotation/data/latest.json
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REQUIRED = {"date", "minute", "code", "industry", "open", "close", "volume_lots"}
SECTORS = {"半導體","電子代工","PCB","AI伺服器","記憶體","散熱","光通訊","電源管理","被動元件","機器人","網通","航運","金融","生技","工具機"}

def load_mapping():
    path = Path(__file__).parent / "data" / "stock_industry_map.csv"
    if not path.exists():
        raise ValueError("Missing stock_industry_map.csv")
    with path.open(encoding="utf-8-sig", newline="") as f:
        result = {}
        for row in csv.DictReader(f):
            code = row["code"].strip()
            sector = row["industry"].strip()
            if not code or sector not in SECTORS or code in result:
                raise ValueError("Invalid/duplicate stock mapping: " + code)
            result[code] = sector
    return result
TIMES = [f"{9 + i // 60:02d}:{i % 60:02d}" for i in range(265)]
TIME_SET = set(TIMES)

def build(source):
    with open(source, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError("Missing CSV columns: " + ", ".join(sorted(REQUIRED - set(reader.fieldnames or []))))
        rows = list(reader)
    if not rows:
        raise ValueError("Empty CSV")
    dates = {r["date"] for r in rows}
    if len(dates) != 1:
        raise ValueError("Expected one trading date per file")
    day = dates.pop()
    datetime.strptime(day, "%Y-%m-%d")
    mapping = load_mapping()
    seen = set()
    stock_minutes = defaultdict(set)
    industry_by_stock = {}
    records = []
    for row in rows:
        minute = row["minute"][-5:]
        if minute not in TIME_SET:
            raise ValueError("Unexpected minute: " + row["minute"])
        code = row["code"].strip()
        industry = row["industry"].strip()
        if not code or not industry:
            raise ValueError("Missing code or industry")
        if code not in mapping:
            raise ValueError("Unclassified stock: " + code + " (add to stock_industry_map.csv after verification)")
        if mapping[code] != industry:
            raise ValueError("Sector mapping conflict: " + code + " CSV=" + industry + " registry=" + mapping[code])
        key = (code, minute)
        if key in seen:
            raise ValueError("Duplicate stock/minute: " + str(key))
        seen.add(key)
        if code in industry_by_stock and industry_by_stock[code] != industry:
            raise ValueError("Industry changed for " + code)
        industry_by_stock[code] = industry
        o, c, v = (float(row[k]) for k in ("open", "close", "volume_lots"))
        if not (0 < o < float("inf") and 0 < c < float("inf") and 0 <= v < float("inf")):
            raise ValueError("Invalid numeric values: " + str(key))
        stock_minutes[code].add(minute)
        records.append({"minute": minute, "code": code, "industry": industry, "open": o, "close": c, "volume_lots": v})
    partial = {code: len(minutes) for code, minutes in stock_minutes.items() if len(minutes) != 265}
    return {
        "schema_version": 1, "date": day,
        "status": "SHADOW_PARTIAL" if partial else "SHADOW_COVERAGE_UNVERIFIED",
        "measurement": "equal_weight_industry_return_minus_sample_equal_weight_return",
        "volume_unit_verified": False,
        "coverage": {"rows": len(records), "stocks": len(stock_minutes),
                     "industries": len(set(industry_by_stock.values())),
                     "minutes": len(set(r["minute"] for r in records)),
                     "partial_stocks": partial, "market_wide": False},
        "rows": records
    }

def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: build_daily_data.py INPUT.csv OUTPUT.json")
    result = build(sys.argv[1])
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("date", "status", "coverage")}, ensure_ascii=False))

if __name__ == "__main__":
    main()
