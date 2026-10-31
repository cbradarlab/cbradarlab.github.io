#!/usr/bin/env python3
"""Read-only Shioaji historical K-bar export for the PCB SHADOW watchlist.

Requires a locally installed Shioaji and existing authenticated session.
Does NOT log in, trade, place orders, write GitHub, or modify production data.
Use as a library: export(api, "2026-10-30", "output.csv").
Kbars are historical snapshots, NOT verified realtime 1-minute ticks.
"""
import csv
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WATCHLIST = ROOT / "data" / "pcb_minute_watchlist_shadow.csv"

def export(api, trading_day, output, *, watchlist=WATCHLIST):
    date.fromisoformat(trading_day)
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite: {output}")
    with Path(watchlist).open(encoding="utf-8-sig", newline="") as f:
        stocks = list(csv.DictReader(f))
    if not stocks or len({r["code"] for r in stocks}) != len(stocks):
        raise ValueError("Empty or duplicate PCB watchlist")
    records, failures = [], []
    for stock in stocks:
        code = stock["code"]
        stock_records = []
        try:
            contract = api.Contracts.Stocks[code]
            kb = api.kbars(contract=contract, start=trading_day, end=trading_day)
            # Shioaji kbars fields: ts, Open, High, Low, Close, Volume.
            # Preserve RAW values: do not infer lots, fabricate zero-volume bars,
            # or assume all 265/270 minutes must be present.
            fields = (kb.ts, kb.Open, kb.High, kb.Low, kb.Close, kb.Volume)
            if len({len(field) for field in fields}) != 1:
                raise ValueError("Inconsistent K-bar field lengths")
            for ts, o, h, l, c, vol in zip(*fields):
                timestamp = str(ts)
                if not timestamp.startswith(trading_day):
                    continue
                stock_records.append((trading_day, code, stock["name"], timestamp,
                                      o, h, l, c, vol))
            records.extend(stock_records)
        except Exception as exc:
            failures.append({"code": code, "error_type": type(exc).__name__})
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "code", "name", "timestamp", "open", "high", "low", "close", "volume_raw"])
        writer.writerows(records)
    return {"date": trading_day, "watchlist_stocks": len(stocks),
            "stocks_with_rows": len({r[1] for r in records}),
            "rows": len(records), "failed": failures,
            "volume_unit_verified": False, "ready_for_rotation": False}

if __name__ == "__main__":
    raise SystemExit("Import export(api, date, output) into an already authenticated local Shioaji session; no credentials are accepted here.")
