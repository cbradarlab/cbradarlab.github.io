#!/usr/bin/env python3
"""Daily SHADOW full-market K-bar coverage audit; metadata only, no OHLCV export."""
import json, os, sys, time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import shioaji as sj
from shadow_full_market_batch_probe import universe

TZ=ZoneInfo("Asia/Taipei")
def target_date():
    today=datetime.now(TZ).date()
    value=os.getenv("TRADE_DATE","").strip()
    if value:
        from datetime import date
        d=date.fromisoformat(value)
        if d>today:raise ValueError("future TRADE_DATE")
    else:
        d=today
        while d.weekday()>=5:d-=timedelta(days=1)
    if d.weekday()>=5:raise ValueError("weekend is not a trading date")
    return d.isoformat()

def main():
    date=target_date()
    if not os.getenv("SHIOAJI_API_KEY") or not os.getenv("SHIOAJI_SECRET_KEY"):
        print("HOLD: missing API credentials");return 2
    api=sj.Shioaji(simulation=False)
    result={"date":date,"status":"HOLD","market_stats":{"TSE":{"requested":0,"with_bars":0},"OTC":{"requested":0,"with_bars":0}},
            "empty_codes":[],"exception_codes":[],"raw_ohlcv_exported":False,"production_ready":False}
    try:
        api.login(api_key=os.environ["SHIOAJI_API_KEY"],secret_key=os.environ["SHIOAJI_SECRET_KEY"],subscribe_trade=False)
        candidates=universe(api)
        result["candidate_count"]=len(candidates)
        start=time.monotonic()
        budget=int(os.getenv("MAX_SECONDS","900"))
        for market,code,contract in candidates:
            if time.monotonic()-start>=budget:
                result["stop_reason"]="time_budget";break
            try:
                bars=api.kbars(contract,start=date,end=date)
                count=len(bars.ts)
                if count:result["market_stats"][market]["with_bars"]+=1
                else:result["empty_codes"].append({"market":market,"code":code})
            except Exception as exc:
                result["exception_codes"].append({"market":market,"code":code,"type":type(exc).__name__})
            result["market_stats"][market]["requested"]+=1
        result["requested"]=sum(v["requested"] for v in result["market_stats"].values())
        result["with_bars"]=sum(v["with_bars"] for v in result["market_stats"].values())
        result["elapsed_seconds"]=round(time.monotonic()-start,2)
        result["coverage"]=round(result["with_bars"]/result["requested"],5) if result["requested"] else 0
        complete=result["requested"]==len(candidates)
        result["status"]="PASS_COVERAGE_SHADOW" if complete and not result["exception_codes"] and result["coverage"]>=0.98 else "HOLD_REVIEW_SHADOW"
        print("SUMMARY",json.dumps({k:v for k,v in result.items() if k not in ("empty_codes","exception_codes")},ensure_ascii=False))
        print("EMPTY",len(result["empty_codes"]),"ERRORS",len(result["exception_codes"]))
        return 0 if result["status"]=="PASS_COVERAGE_SHADOW" else 3
    except Exception as exc:
        result["error"]=type(exc).__name__+": "+str(exc)[:160]
        print("HOLD",result["error"])
        return 3
    finally:
        Path("daily_market_coverage_shadow.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        try:api.logout()
        except Exception:pass
if __name__=="__main__":sys.exit(main())
