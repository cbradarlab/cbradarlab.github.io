#!/usr/bin/env python3
"""Read-only, manually triggered SHADOW Shioaji cloud quote probe.
No trade subscriptions, orders, production data writes, or raw-price uploads.
"""
import os,sys
from datetime import datetime,timedelta
import shioaji as sj
DAY=os.environ.get("PROBE_DATE","2026-10-30")
CODES=("3037","1303")
def timestamp(ts):
    if isinstance(ts,datetime):return ts
    try:return datetime(1970,1,1)+timedelta(microseconds=int(ts)//1000)
    except (TypeError,ValueError):
        return datetime.fromisoformat(str(ts).replace("T"," "))
def main():
    key=os.environ.get("SHIOAJI_API_KEY")
    secret=os.environ.get("SHIOAJI_SECRET_KEY")
    if not key or not secret:
        print("HOLD: missing secrets");return 2
    api=sj.Shioaji(simulation=False)
    try:
        api.login(api_key=key,secret_key=secret,subscribe_trade=False)
        checks=[]
        for code in CODES:
            kb=api.kbars(api.Contracts.Stocks[code],start=DAY,end=DAY)
            fields=(kb.ts,kb.Open,kb.High,kb.Low,kb.Close,kb.Volume)
            if len({len(x) for x in fields})!=1:raise ValueError("K-bar lengths differ")
            stamps=[timestamp(x) for x in kb.ts]
            same_day=[t for t in stamps if t.date().isoformat()==DAY]
            auction=sum(t.strftime("%H:%M")=="13:30" for t in same_day)
            continuous=sum("09:01"<=t.strftime("%H:%M")<="13:25" for t in same_day)
            print(f"STOCK {code}: date_match={len(same_day)}, continuous={continuous}, auction_1330={auction}")
            checks.append(bool(continuous) and auction==1)
        if not all(checks):print("HOLD: incomplete cloud quote result");return 3
        print("PASS: cloud historical kbars for 2 pilot stocks, with separate 13:30 auction")
        return 0
    except Exception as exc:
        print("FAIL: cloud quote probe "+type(exc).__name__)
        return 1
    finally:
        try:api.logout()
        except Exception:pass
if __name__=="__main__":sys.exit(main())
