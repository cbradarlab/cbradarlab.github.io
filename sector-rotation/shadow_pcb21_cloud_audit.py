#!/usr/bin/env python3
"""PCB21 cloud daily SHADOW coverage audit. Read-only Shioaji; no trades or raw data publication."""
import csv,json,os,sys
from pathlib import Path
from datetime import datetime,timedelta\nfrom zoneinfo import ZoneInfo
import shioaji as sj
ROOT=Path(__file__).resolve().parent
WATCHLIST=ROOT/"data"/"pcb_minute_watchlist_shadow.csv"
def parse_ts(ts):
    if isinstance(ts,datetime): return ts
    try: return datetime(1970,1,1)+timedelta(microseconds=int(ts)//1000)
    except (TypeError,ValueError): return datetime.fromisoformat(str(ts).replace("T"," "))
def audit(api,day,watchlist=WATCHLIST):
    names=list(csv.DictReader(open(watchlist,encoding="utf-8-sig",newline="")))
    if len(names)!=21 or len(set(x["code"] for x in names))!=21:raise ValueError("Watchlist must contain 21 unique codes")
    outcome=[]
    for stock in names:
        code=stock["code"]
        try:
            contract=api.Contracts.Stocks[code]
            kb=api.kbars(contract,start=day,end=day)
            fields=(kb.ts,kb.Open,kb.High,kb.Low,kb.Close,kb.Volume)
            if len({len(a) for a in fields})!=1: raise ValueError("field_length_mismatch")
            minutes=set(); auction=0; records=0; duplicates=0; bad=0
            for ts,o,h,l,c,v in zip(*fields):
                t=parse_ts(ts)
                if t.date().isoformat()!=day:continue
                label=t.strftime("%H:%M")
                if not ("09:01"<=label<="13:25" or label=="13:30"):continue
                vals=[float(n) for n in (o,h,l,c,v)]
                if not (vals[2]<=min(vals[0],vals[3])<=max(vals[0],vals[3])<=vals[1] and vals[4]>=0):bad+=1
                if label=="13:30":auction+=1
                else:
                    if label in minutes:duplicates+=1
                    minutes.add(label)
                records+=1
            good=len(minutes)>0 and auction==1 and duplicates==0 and bad==0
            outcome.append({"code":code,"intraday_bars":len(minutes),"missing_intraday_slots":265-len(minutes),"auction_1330":auction,"duplicate_intraday":duplicates,"invalid_ohlcv":bad,"status":"PASS" if good else "HOLD"})
        except Exception as exc:
            outcome.append({"code":code,"status":"HOLD","error_type":type(exc).__name__})
    return {"date":day,"scope":"PCB21_SHADOW","stocks":len(outcome),"passed":sum(x["status"]=="PASS" for x in outcome),"status":"PASS_COVERAGE_STRUCTURE_SHADOW" if all(x["status"]=="PASS" for x in outcome) else "HOLD","market_volume_verified":False,"production_ready":False,"stocks_detail":outcome}
def main():
    day=os.environ.get("TRADE_DATE") or datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat()
    if datetime.strptime(day,"%Y-%m-%d").weekday()>=5:
        print("HOLD: weekend; no quote fetch");return 0
    key=os.environ.get("SHIOAJI_API_KEY");secret=os.environ.get("SHIOAJI_SECRET_KEY")
    if not key or not secret:print("HOLD: missing secrets");return 2
    api=sj.Shioaji(simulation=False)
    try:
        api.login(api_key=key,secret_key=secret,subscribe_trade=False)
        summary=audit(api,day)
        output=Path(os.environ.get("GITHUB_WORKSPACE","."))/"pcb21_coverage_summary_shadow.json"
        output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("SUMMARY",summary["date"],summary["status"],summary["passed"],"/21")
        for s in summary["stocks_detail"]:print("STOCK",s["code"],s["status"],s.get("intraday_bars"),s.get("auction_1330"))
        return 0 if summary["status"]=="PASS_COVERAGE_STRUCTURE_SHADOW" else 3
    finally:
        try:api.logout()
        except Exception:pass
if __name__=="__main__":sys.exit(main())
