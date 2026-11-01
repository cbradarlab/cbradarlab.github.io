#!/usr/bin/env python3
"""Official TWSE/TPEx listed-company stock-code universe; fail closed on schema drift."""
import json,re,sys,urllib.request
from pathlib import Path
SOURCES={
 "TSE":"https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
 "OTC":"https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
}
CODE_KEYS=("公司代號","公司代碼","證券代號","Code")
NAME_KEYS=("公司名稱","公司簡稱","Name")
def load(url):
 req=urllib.request.Request(url,headers={"User-Agent":"CBRadar-SectorRotation-Shadow/1.0","Accept":"application/json"})
 with urllib.request.urlopen(req,timeout=30) as response:
  data=json.load(response)
 if not isinstance(data,list) or not data or not isinstance(data[0],dict):
  raise ValueError("unexpected official JSON schema")
 return data
def field(row,keys):
 for key in keys:
  if key in row:return str(row[key]).strip()
 return None
def main():
 result={"status":"HOLD","sources":SOURCES,"markets":{},"excluded_non_4_digit":{},"equity_only_verified":False}
 try:
  for market,url in SOURCES.items():
   rows=load(url);codes={};excluded=0
   if not any(k in rows[0] for k in CODE_KEYS):raise ValueError(market+": company-code field missing")
   for row in rows:
    code=field(row,CODE_KEYS);name=field(row,NAME_KEYS)
    if code and re.fullmatch(r"[0-9]{4}",code):
     if code in codes and codes[code]!=name:raise ValueError(market+": conflicting company codes "+code)
     codes[code]=name
    else:excluded+=1
   if len(codes)<300:raise ValueError(market+": unexpectedly small official company count "+str(len(codes)))
   result["markets"][market]={"count":len(codes),"codes":sorted(codes),"sample":sorted(codes)[:5]}
   result["excluded_non_4_digit"][market]=excluded
  result["status"]="PASS_OFFICIAL_LISTED_COMPANY_UNIVERSE_SHADOW"
  result["equity_only_verified"]=False
 except Exception as exc:
  result["error"]=type(exc).__name__+": "+str(exc)[:240]
 Path("official_equity_universe_shadow.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("SUMMARY",json.dumps({k:v for k,v in result.items() if k!="markets"},ensure_ascii=False))
 for m,v in result["markets"].items():print("MARKET",m,"company_codes",v["count"],"sample",v["sample"])
 return 0 if result["status"].startswith("PASS") else 3
if __name__=="__main__":sys.exit(main())
