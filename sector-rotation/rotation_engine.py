#!/usr/bin/env python3
"""Conservative rotation engine. No output until 21 verified trading sessions exist."""
import json,pathlib,statistics,datetime
ROOT=pathlib.Path(__file__).resolve().parent
STATUS="verified_quote_source_trade_date"
def compute(history,stocks):
 valid=sorted((x for x in history if x.get("date_status")==STATUS and x.get("trade_date") and isinstance(x.get("quotes"),dict)),key=lambda x:x["trade_date"])
 dates=[x["trade_date"] for x in valid]
 if len(dates)!=len(set(dates)):raise ValueError("duplicate trade dates")
 if len(valid)<21:return {"status":"HOLD_INSUFFICIENT_VERIFIED_SESSIONS","verified_sessions":len(valid),"required_sessions":21,"groups":[]}
 valid=valid[-21:]
 meta={s["id"]:s for s in stocks if s.get("industry") and s.get("id")}
 by_industry={}
 for code,s in meta.items():
  prices=[day["quotes"].get(code,{}).get("close") for day in valid]
  if any(not isinstance(p,(int,float)) or p<=0 for p in prices):continue
  group=(s.get("market",""),s["industry"])
  by_industry.setdefault(group,[]).append((prices[-1]/prices[-21]-1,prices[-1]/prices[-6]-1))
 groups=[]
 for (market,industry),values in sorted(by_industry.items()):
  if len(values)<5:continue
  groups.append({"market":market,"industry":industry,"members":len(values),"return_20d":round(statistics.median(x[0] for x in values)*100,3),"return_5d":round(statistics.median(x[1] for x in values)*100,3)})
 if len(groups)<5:return {"status":"HOLD_INSUFFICIENT_INDUSTRY_COVERAGE","verified_sessions":len(valid),"groups":[]}
 benchmark_20=statistics.median(x["return_20d"] for x in groups)
 benchmark_5=statistics.median(x["return_5d"] for x in groups)
 for x in groups:
  x["relative_strength"]=round(x["return_20d"]-benchmark_20,3)
  x["relative_momentum"]=round(x["return_5d"]-benchmark_5,3)
  x["quadrant"]=("領先" if x["relative_strength"]>=0 else "改善") if x["relative_momentum"]>=0 else ("轉弱" if x["relative_strength"]>=0 else "落後")
 return {"status":"SHADOW_READY","verified_sessions":len(valid),"first_trade_date":valid[0]["trade_date"],"last_trade_date":valid[-1]["trade_date"],"method":"industry median 20/5 session returns relative to cross-industry median; not RRG JdK","groups":groups}
def main():
 data=ROOT/"data"
 history=json.loads((data/"quotes_history.json").read_text(encoding="utf-8"))
 stocks=json.loads((data/"stocks.json").read_text(encoding="utf-8"))["stocks"]
 result=compute(history,stocks)
 out=data/"rotation_shadow.json"
 out.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
 print(result["status"],"verified_sessions",result["verified_sessions"],"groups",len(result["groups"]))
if __name__=="__main__":main()
