#!/usr/bin/env python3
"""Daily official close snapshot. No fabricated prices; retain last good on failures."""
import datetime,json,pathlib,urllib.request,urllib.error,re,hashlib,time
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
  # Retry incomplete/invalid official responses; never publish a partial JSON payload.
  data=None
  for attempt in range(1,5):
   try:
    with urllib.request.urlopen(req,timeout=50) as response:
     raw=response.read(20000001)
    if len(raw)>20000000:raise ValueError("response too large")
    candidate=json.loads(raw.decode("utf-8-sig"))
    if not isinstance(candidate,list):raise ValueError("expected JSON array")
    data=candidate
    break
   except (urllib.error.URLError,TimeoutError,UnicodeError,json.JSONDecodeError,ValueError) as e:
    print("SOURCE_RETRY",market,attempt,type(e).__name__,str(e)[:180],flush=True)
    if attempt==4:raise
    time.sleep(min(attempt*3,12))
  rows={}
  for x in data:
   if not isinstance(x,dict):continue
   code=get(x,"Code","SecuritiesCompanyCode","股票代號","證券代號","SecuritiesCode")
   close=price(get(x,"ClosingPrice","Close","收盤價","ClosePrice"))
   if re.fullmatch(r"\d{4}",code or "") and close:
    rows[code]={"close":close,"market":market}
  print("SOURCE_SCHEMA",market,"raw",len(data),"valid",len(rows),"keys",list(data[0].keys()) if data and isinstance(data[0],dict) else [],flush=True)
  if len(rows)<300:
   print("SOURCE_SAMPLE",market,str(data[0])[:850] if data else "EMPTY",flush=True)
   raise ValueError("invalid quote coverage "+market+" "+str(len(rows)))
  out.update(rows);counts[market]=len(rows)
 if len(out)<1000:raise ValueError("insufficient total quotes")
 dest=ROOT/"data"/"quotes_latest.json";dest.parent.mkdir(exist_ok=True)
 history_path=ROOT/"data"/"quotes_history.json"
 history=[]
 if history_path.exists():
  old=json.loads(history_path.read_text(encoding="utf-8"))
  if isinstance(old,list):history=old
  else:raise ValueError("invalid existing history format")
 if history and now.isoformat()[:10]<str(history[-1].get("snapshot_date","")):raise ValueError("snapshot clock older than history") 
 # Check TWSE's official trading-day index for the current Taiwan calendar date.
 # This check is independent of quote price changes and catches stale holiday feeds.
 def official_twse_trade_day(day):
  url="https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date="+day.strftime("%Y%m%d")
  req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
  with urllib.request.urlopen(req,timeout=40) as response:
   data=json.loads(response.read(2000000).decode("utf-8-sig"))
  if data.get("stat")!="OK" or not isinstance(data.get("data"),list):
   raise ValueError("TWSE FMTQIK calendar unavailable: "+str(data.get("stat")))
  roc=f"{day.year-1911}/{day.month:02d}/{day.day:02d}"
  matched=[r for r in data["data"] if isinstance(r,list) and r and str(r[0]).strip()==roc]
  return bool(matched)
 try:
  is_trade_day=official_twse_trade_day(now.date())
 except Exception as e:
  print("HOLD_CALENDAR_UNVERIFIED",type(e).__name__,str(e)[:220],flush=True)
  return
 if not is_trade_day:
  print("SKIP_OFFICIAL_NON_TRADING_DAY",now.date().isoformat(),flush=True)
  return
 print("PASS_TWSE_TRADE_DATE",now.date().isoformat(),flush=True)
 # Same complete closing-price snapshot on a later date indicates a stale/holiday feed.
 # Never count it as a new trading day; source trade date remains unverified.
 def fingerprint(quotes):
  values={k:v["close"] for k,v in sorted(quotes.items())}
  return hashlib.sha256(json.dumps(values,sort_keys=True,separators=(",",":")).encode()).hexdigest()
 current_hash=fingerprint(out)
 earlier=[x for x in history if x.get("snapshot_date")!=now.date().isoformat()]
 if earlier and current_hash==fingerprint(earlier[-1]["quotes"]):
  print("SKIP_STALE_IDENTICAL_QUOTES",now.date().isoformat(),"previous",earlier[-1]["snapshot_date"],flush=True)
  return
 print("QUOTE_FINGERPRINT",current_hash,flush=True)
 payload={"fetched_at":now.isoformat(),"date_status":"twse_calendar_verified_quotes_source_date_unverified","price_fingerprint":current_hash,"counts":counts,"sources":FEEDS,"quotes":out}
 tmp=dest.with_suffix(".tmp");tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8");tmp.replace(dest)
 # Snapshot archive is keyed by fetch date, NOT verified exchange trading date.
 record={"snapshot_date":now.date().isoformat(),"fetched_at":now.isoformat(),"date_status":"twse_calendar_verified_quotes_source_date_unverified","price_fingerprint":current_hash,"quotes":out}
 # Upgrade legacy same-day entry after calendar verification, even when prices are identical.
 # Keep archive records explicitly keyed to capture date rather than claiming quote-source date.
 history=[x for x in history if x.get("snapshot_date")!=record["snapshot_date"]]+[record]
 print("ARCHIVE_RECORD_STATUS",record["snapshot_date"],record["date_status"],flush=True)
 history=history[-180:]
 hist_tmp=history_path.with_suffix(".tmp");hist_tmp.write_text(json.dumps(history,ensure_ascii=False,separators=(",",":")),encoding="utf-8");hist_tmp.replace(history_path)
 print("PASS quote snapshot",counts,"NOTE: date not verified; do not label as today's close")
if __name__=="__main__":main()
