#!/usr/bin/env python3
"""Build SHADOW sector-minute frames from a private Shioaji sample artifact.
Not a licensed/public real-time feed. Does not upload quotes to Pages.
"""
import json
from collections import defaultdict
from pathlib import Path
from urllib.request import urlopen

SOURCE=Path("intraday_player_feed_shadow.json")
OUTPUT=Path("sector_minute_aggregate_shadow.json")
MASTER_URL="https://cbradarlab.github.io/sector-rotation/data/stocks.json"

def clock(value):
    s=str(value)
    if "T" in s:s=s.split("T",1)[1]
    elif " " in s:s=s.split(" ",1)[1]
    return s[:5]

def main():
    data=json.loads(SOURCE.read_text(encoding="utf-8"))
    with urlopen(MASTER_URL,timeout=20) as r:master=json.load(r)
    lookup={str(s["id"]):s for s in master["stocks"]}
    bytime=defaultdict(lambda:defaultdict(list))
    usable=0
    for stock in data["stocks"]:
        info=lookup.get(str(stock["code"]))
        if not info or not stock.get("minutes"):continue
        sector=str(info.get("industry") or "未分類")
        points=sorted(stock["minutes"],key=lambda x:str(x["t"]))
        first=float(points[0]["c"])
        if first<=0:continue
        usable+=1
        total_vol=0
        for p in points:
            price=float(p["c"]);vol=float(p["v"])
            if price<=0 or vol<0:continue
            total_vol+=vol
            bytime[clock(p["t"])][sector].append((100*(price/first-1),total_vol))
    # Hold last known state of each stock through minutes with no trade.
    # Sample-level aggregate is not full-sector coverage.
    frames=[]
    for t in sorted(bytime):
        groups=[]
        for sector,values in sorted(bytime[t].items()):
            groups.append({"industry":sector,"name":"產業 "+sector,
                           "strength":round(sum(v[0] for v in values)/len(values),4),
                           "activity":round(sum(v[1] for v in values),2),
                           "sample_stocks":len(values)})
        frames.append({"time":t,"industries":groups})
    out={"trade_date":data["date"],"generated_at":data["generated_at"],
         "status":"SAMPLE_ONLY_SHADOW","production_ready":False,
         "publish_permitted":False,"usable_stocks":usable,
         "strength_definition":"equal-weighted return from each stock first observed minute",
         "activity_definition":"sum of sampled stocks cumulative reported volume",
         "frames":frames}
    OUTPUT.write_text(json.dumps(out,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print("SECTOR_SUMMARY",json.dumps({"usable_stocks":usable,
          "frames":len(frames),"industries":len({x["industry"] for f in frames for x in f["industries"]})}))
    if usable<1 or not frames:raise RuntimeError("No usable stock minute data")
if __name__=="__main__":main()
