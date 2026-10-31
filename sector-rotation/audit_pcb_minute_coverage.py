#!/usr/bin/env python3
"""Read-only SHADOW audit: PCB role stock coverage in a minute snapshot.
Usage: python sector-rotation/audit_pcb_minute_coverage.py sector-rotation/data/latest.json
Never treats a missing stock as a zero return or a covered stock.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def audit(snapshot):
    with (ROOT / "data/pcb_chain_roles_shadow.csv").open(encoding="utf-8-sig", newline="") as f:
        roles = list(csv.DictReader(f))
    groups = defaultdict(set)
    for r in roles:
        groups[r["subchain"]].add(r["code"])
    with Path(snapshot).open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data.get("rows"), list):
        raise ValueError("Snapshot has no minute rows")
    by_stock = defaultdict(set)
    for row in data["rows"]:
        if row.get("code") and row.get("minute"):
            by_stock[str(row["code"])].add(row["minute"])
    result = {"status": "SHADOW_COVERAGE_ONLY", "date": data.get("date"),
              "snapshot_status": data.get("status"), "market_wide": data.get("coverage", {}).get("market_wide", False),
              "expected_minutes": 265, "groups": {}}
    for group, members in sorted(groups.items()):
        complete = sorted(c for c in members if len(by_stock[c]) == 265)
        partial = {c: len(by_stock[c]) for c in sorted(members) if 0 < len(by_stock[c]) < 265}
        missing = sorted(c for c in members if not by_stock[c])
        result["groups"][group] = {"members": len(members), "complete": len(complete),
                                    "complete_codes": complete, "partial": partial, "missing": missing,
                                    "complete_pct": round(100 * len(complete) / len(members), 2)}
    result["ready_for_rotation"] = False
    result["reason"] = "Coverage audit alone cannot validate market-wide minute flow, units or lead-lag."
    return result

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: audit_pcb_minute_coverage.py SNAPSHOT.json")
    print(json.dumps(audit(sys.argv[1]), ensure_ascii=False, indent=2))
