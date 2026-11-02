#!/usr/bin/env python3
"""Private SHADOW sample-sector frames; never publish licensed market data."""
import json
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

SOURCE = Path("intraday_player_feed_shadow.json")
MASTER = Path("sector-rotation/data/stocks.json")
OUTPUT = Path("sector_minute_aggregate_shadow.json")

def minute(value):
    s = str(value)
    if s.isdigit() and len(s) >= 13:
        # Shioaji numpy datetime64[ns] is serialized as epoch nanoseconds.
        return datetime.fromtimestamp(int(s) / 1_000_000_000, ZoneInfo("Asia/Taipei")).strftime("%H:%M")
    if "T" in s:
        s = s.split("T", 1)[1]
    elif " " in s:
        s = s.split(" ", 1)[1]
    return s[:5]

def build(data, master):
    lookup = {str(s["id"]): s for s in master["stocks"]}
    histories = []
    timeline = set()
    for stock in data.get("stocks", []):
        info = lookup.get(str(stock.get("code")))
        if not info:
            continue
        bars = sorted(stock.get("minutes", []), key=lambda x: str(x["t"]))
        valid = []
        for p in bars:
            price, vol = float(p["c"]), float(p["v"])
            if price > 0 and vol >= 0:
                valid.append((minute(p["t"]), price, vol))
        if not valid:
            continue
        timeline.update(t for t, _, _ in valid)
        histories.append((str(info.get("industry") or "未分類"), valid))
    cursors = [0] * len(histories)
    last = [None] * len(histories)
    volume = [0.] * len(histories)
    frames = []
    for t in sorted(timeline):
        groups = defaultdict(list)
        for i, (sector, bars) in enumerate(histories):
            while cursors[i] < len(bars) and bars[cursors[i]][0] <= t:
                _, price, v = bars[cursors[i]]
                volume[i] += v
                last[i] = price
                cursors[i] += 1
            if last[i] is not None:
                base = bars[0][1]
                groups[sector].append((100 * (last[i] / base - 1), volume[i]))
        industries = [
            {"industry": sector, "name": "產業 " + sector,
             "strength": round(sum(v[0] for v in vals) / len(vals), 4),
             "activity": round(sum(v[1] for v in vals), 2),
             "sample_stocks": len(vals)}
            for sector, vals in sorted(groups.items())
        ]
        frames.append({"time": t, "industries": industries})
    return {
        "trade_date": data["date"], "generated_at": data["generated_at"],
        "status": "SAMPLE_ONLY_SHADOW", "production_ready": False,
        "publish_permitted": False, "usable_stocks": len(histories),
        "strength_definition": "equal-weight return since first observed minute, with last trade carried forward",
        "activity_definition": "sum of sampled stocks cumulative volume",
        "frames": frames
    }

def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    result = build(data, master)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("SECTOR_SUMMARY", json.dumps({
        "usable_stocks": result["usable_stocks"], "frames": len(result["frames"]),
        "industries": len({x["industry"] for f in result["frames"] for x in f["industries"]})
    }))
    if not result["frames"]:
        raise RuntimeError("No usable minute data")

if __name__ == "__main__":
    main()
