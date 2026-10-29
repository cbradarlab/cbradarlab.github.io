#!/usr/bin/env python3
"""Daily official close snapshot. No fabricated prices; retain last good on failures."""
import datetime,json,pathlib,urllib.request,urllib.error,re
ROOT=pathlib.Path(__file__).resolve().parent
FEEDS={"上市":"https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL","上櫃":"https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"}
def get(o,*keys):
 for k in keys:
  v=o.get(k)
  if v is not None and str(v).strip():return str(v).strip()
 return ""
def price(s):
 try:
  v=float(str(s).replace(",","").replace("+",""))
  return v if 0<v<100000 else None
 except (ValueError,TypeError):return None
def main():
 now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
 if now.weekday()>=5:print("SKIP non-trading weekend");return
 out={};counts={}
 for market,url in FEEDS.items():
  req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","Accept-Language":"zh-TW"})
  try:
   with urllib.request.urlopen(req,timeout=50) as response:raw=response.read(20000001)
  except Exception as e:
   print("FETCH_FAILED",market,type(e).__name__,str(e)[:200],flush=True);raise
  if len(raw)>20000000:raise ValueError("response too large")
  data=json.loads(raw.decode("utf-8-sig"))
  if not isinstance(data,list):raise ValueError("expected JSON array")
  rows={}
  for x in data:
   if not isinstance(x,dict):continue
   code=get(x,"Code","SecuritiesCompanyCode","股票代號","證券代號","SecuritiesCode")
   close=price(get(x,"ClosingPrice","Close","收盤價","ClosePrice"))
   if re.fullmatch(r"\d{4}",code or "") and close:
    rows[code]={"close":close,"market":market}
  print("SOURCE_SCHEMA",market,"raw",len(data),"valid",len(rows),"keys",list(data[0].keys()) if data and isinstance(data[0],dict) else [],flush=True)
  if len(rows)<300:raise ValueError("invalid quote coverage "+market+" "+str(len(rows)))
  out.update(rows);counts[market]=len(rows)
 if len(out)<1000:raise ValueError("insufficient total quotes")
 dest=ROOT/"data"/"quotes_latest.json";dest.parent.mkdir(exist_ok=True)
 payload={"fetched_at":now.isoformat(),"date_status":"unverified_exchange_trade_date","counts":counts,"sources":FEEDS,"quotes":out}
 tmp=dest.with_suffix(".tmp");tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8");tmp.replace(dest)
 print("PASS quote snapshot",counts,"NOTE: date not verified; do not label as today's close")
if __name__=="__main__":main()
