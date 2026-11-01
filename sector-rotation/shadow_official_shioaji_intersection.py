#!/usr/bin/env python3
"""Manual-only read-only reconciliation of official listed companies vs Shioaji contracts."""
import json,os,re,sys
from pathlib import Path
import shioaji as sj
from shadow_official_equity_universe import SOURCES,CODE_KEYS_BY_MARKET,load,field
def main():
 result={"status":"HOLD","official_counts":{},"shioaji_counts":{},"matched_counts":{},"missing_official_in_shioaji":{},"shioaji_not_official":{},"market_mismatches":[],"source":"official TWSE/TPEx company registries x Shioaji stock contracts","no_quotes_requested":True,"orders_placed":False,"production_ready":False}
 api=None
 try:
  official={}
  for market,url in SOURCES.items():
   rows=load(url)
   keys=CODE_KEYS_BY_MARKET[market]
   if not any(k in rows[0] for k in keys):raise ValueError(market+" code field absent")
   codes={field(row,keys) for row in rows}
   official[market]={c for c in codes if c and re.fullmatch(r"[0-9]{4}",c)}
   if len(official[market])<300:raise ValueError(market+" official count suspicious")
   result["official_counts"][market]=len(official[market])
  if not os.getenv("SHIOAJI_API_KEY") or not os.getenv("SHIOAJI_SECRET_KEY"):raise ValueError("missing Shioaji secrets")
  api=sj.Shioaji(simulation=False)
  api.login(api_key=os.environ["SHIOAJI_API_KEY"],secret_key=os.environ["SHIOAJI_SECRET_KEY"],subscribe_trade=False)
  available={"TSE":set(),"OTC":set()}
  for group in api.Contracts.Stocks:
   for contract in group:
    code=str(getattr(contract,"code",""))
    market=str(getattr(contract,"exchange","")).upper()
    if market in available and re.fullmatch(r"[0-9]{4}",code):
     available[market].add(code)
  for market in ("TSE","OTC"):
   both=official[market]&available[market]
   result["shioaji_counts"][market]=len(available[market])
   result["matched_counts"][market]=len(both)
   result["missing_official_in_shioaji"][market]=sorted(official[market]-available[market])
   result["shioaji_not_official"][market]=sorted(available[market]-official[market])
  for market,other in (("TSE","OTC"),("OTC","TSE")):
   for code in sorted(official[market]&available[other]):
    result["market_mismatches"].append({"code":code,"official":market,"shioaji":other})
  result["status"]="PASS_INTERSECTION_AUDIT_SHADOW"
 except Exception as exc:
  result["error"]=type(exc).__name__+": "+str(exc)[:240]
 finally:
  if api:
   try:api.logout()
   except Exception:pass
 Path("official_shioaji_intersection_shadow.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("SUMMARY",json.dumps({k:v for k,v in result.items() if k not in ("missing_official_in_shioaji","shioaji_not_official","market_mismatches")},ensure_ascii=False))
 for market in ("TSE","OTC"):
  print("AUDIT",market,"official_missing",len(result["missing_official_in_shioaji"].get(market,[])),"shioaji_extra",len(result["shioaji_not_official"].get(market,[])))
 print("MARKET_MISMATCHES",len(result["market_mismatches"]))
 return 0 if result["status"].startswith("PASS") else 3
if __name__=="__main__":sys.exit(main())
