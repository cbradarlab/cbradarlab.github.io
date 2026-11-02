#!/usr/bin/env python3
"""Read-only SHADOW probe: bounded Shioaji K-bar requests, no orders or raw price publication."""
import json,os,sys,time
from datetime import datetime,timezone
from pathlib import Path
import shioaji as sj
from shadow_official_equity_universe import SOURCES,CODE_KEYS_BY_MARKET,load,field

DATE=os.getenv("PROBE_DATE","2026-10-30")
BATCH_SIZE=min(2000,max(1,int(os.getenv("BATCH_SIZE","30"))))
MAX_SECONDS=min(900,max(30,int(os.getenv("MAX_SECONDS","150"))))
def universe(api):
    selected={}
    for group in api.Contracts.Stocks:
        for contract in group:
            code=str(getattr(contract,"code",""))
            market=str(getattr(contract,"exchange","")).upper()
            if len(code)==4 and code.isdigit() and market in ("TSE","OTC"):
                selected[(market,code)]=contract
    official={}
    for market,url in SOURCES.items():
        rows=load(url)
        keys=CODE_KEYS_BY_MARKET[market]
        if not rows or not any(k in rows[0] for k in keys):
            raise ValueError("official company schema missing: "+market)
        official[market]={field(row,keys) for row in rows}
        if len(official[market])<300:raise ValueError("official company universe too small: "+market)
    matched=sorted(((m,c,contract) for (m,c),contract in selected.items() if c in official[m]),key=lambda x:(x[0],x[1]))
    if len(matched)<1900:raise ValueError("official/Shioaji intersection unexpectedly small")
    return matched
def main():
    key=os.getenv("SHIOAJI_API_KEY");secret=os.getenv("SHIOAJI_SECRET_KEY")
    if not key or not secret:
        print("HOLD: missing secrets");return 2
    api=sj.Shioaji(simulation=False)
    try:
        api.login(api_key=key,secret_key=secret,subscribe_trade=False)
        candidates=universe(api)
        # Stable stratified sampling: include both TSE and OTC even for small batches.
        def sample(items,n):
            if n<=0:return []
            if n>=len(items):return items
            return [items[(i*len(items))//n] for i in range(n)]
        tse=[x for x in candidates if x[0]=="TSE"]
        otc=[x for x in candidates if x[0]=="OTC"]
        n_tse=min(len(tse),round(BATCH_SIZE*len(tse)/len(candidates)))
        n_otc=min(len(otc),BATCH_SIZE-n_tse)
        target=n_tse+n_otc
        chosen=sample(tse,n_tse)+sample(otc,n_otc)
        print("SAMPLING",json.dumps({"TSE":n_tse,"OTC":n_otc,"total":len(chosen)}))
        elapsed=[];good=0;failures={};minute_counts=[];empty_codes=[];exception_codes=[];market_stats={"TSE":{"requested":0,"with_bars":0},"OTC":{"requested":0,"with_bars":0}}
        started=time.monotonic()
        for market,code,contract in chosen:
            if time.monotonic()-started>=MAX_SECONDS:
                print("HOLD: request time budget reached");break
            start=time.monotonic()
            try:
                bars=api.kbars(contract,start=DATE,end=DATE)
                count=len(bars.ts)
                minute_counts.append(count)
                if count>0:good+=1
                else:
                    failures["empty_bars"]=failures.get("empty_bars",0)+1
                    empty_codes.append({"market":market,"code":code})
                status="OK" if count else "EMPTY"
            except Exception as exc:
                kind=type(exc).__name__
                failures[kind]=failures.get(kind,0)+1
                exception_codes.append({"market":market,"code":code,"type":kind})
                status="ERROR_"+kind
            market_stats[market]["requested"]+=1
            if status=="OK":market_stats[market]["with_bars"]+=1
            elapsed.append(round(time.monotonic()-start,3))
            print("PROBE",market,code,status,"seconds",elapsed[-1])
        result={"date":DATE,"status":("PASS_BATCH_PROBE_SHADOW" if good==target else "PASS_REQUESTS_WITH_EMPTY_BARS_SHADOW") if len(elapsed)==target and not exception_codes else "HOLD","candidate_count":len(candidates),"market_stats":market_stats,"requested":len(elapsed),"successful":good,"target":target,"total_seconds":round(time.monotonic()-started,2),"max_request_seconds":max(elapsed,default=0),"average_request_seconds":round(sum(elapsed)/len(elapsed),3) if elapsed else None,"failures":failures,"empty_codes":empty_codes,"exception_codes":exception_codes,"raw_ohlcv_exported":False,"official_company_intersection_verified":True,"common_stock_only_verified":False,"production_ready":False}
        Path("full_market_batch_performance_shadow.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("SUMMARY",json.dumps(result,ensure_ascii=False))
        return 0 if len(elapsed)==BATCH_SIZE and not exception_codes else 3
    except Exception as exc:
        print("FAIL:",type(exc).__name__);return 1
    finally:
        try:api.logout()
        except Exception:pass
if __name__=="__main__":sys.exit(main())
