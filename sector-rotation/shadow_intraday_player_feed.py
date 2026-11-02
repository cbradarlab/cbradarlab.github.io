#!/usr/bin/env python3
"""Manual SHADOW intraday feed sample. Artifact only; never published to Pages."""
import json, os, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import shioaji as sj
from shadow_full_market_batch_probe import universe

def main():
    now=datetime.now(ZoneInfo("Asia/Taipei"))
    date=os.getenv("TRADE_DATE",now.date().isoformat())
    count=min(30,max(1,int(os.getenv("SAMPLE_COUNT","30"))))
    api=sj.Shioaji(simulation=False)
    report={"date":date,"generated_at":now.isoformat(),"status":"HOLD",
            "sample_target":count,"stocks":[],"errors":[],"production_ready":False}
    try:
        api.login(api_key=os.environ["SHIOAJI_API_KEY"],
                  secret_key=os.environ["SHIOAJI_SECRET_KEY"],subscribe_trade=False)
        pool=universe(api)
        # Spread samples across both exchanges.
        tse=[x for x in pool if x[0]=="TSE"]
        otc=[x for x in pool if x[0]=="OTC"]
        n_tse=round(count*len(tse)/len(pool))
        def pick(xs,n):
            return [xs[(i*len(xs))//n] for i in range(n)] if n else []
        selected=pick(tse,n_tse)+pick(otc,count-n_tse)
        for market,code,contract in selected:
            try:
                bars=api.kbars(contract,start=date,end=date)
                # Keep per-stock timestamp, close, volume for player feed validation.
                # Do not push this data to a public repository or Pages.
                points=[{"t":str(t),"c":float(c),"v":float(v)}
                        for t,c,v in zip(bars.ts,bars.Close,bars.Volume)]
                report["stocks"].append({"market":market,"code":code,"minutes":points})
            except Exception as exc:
                report["errors"].append({"market":market,"code":code,
                                         "type":type(exc).__name__,"detail":str(exc)[:160]})
        report["with_bars"]=sum(bool(s["minutes"]) for s in report["stocks"])
        report["status"]="PASS_SAMPLE_FEED_SHADOW" if len(report["stocks"])==count and not report["errors"] else "HOLD"
        print("SUMMARY",json.dumps({"date":date,"requested":count,
              "with_bars":report["with_bars"],"errors":len(report["errors"]),
              "status":report["status"]},ensure_ascii=False))
        return 0 if report["status"].startswith("PASS") else 3
    except Exception as exc:
        print("HOLD",type(exc).__name__,str(exc)[:120])
        return 3
    finally:
        Path("intraday_player_feed_shadow.json").write_text(
            json.dumps(report,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
        try:api.logout()
        except Exception:pass

if __name__=="__main__":sys.exit(main())
