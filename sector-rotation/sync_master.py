#!/usr/bin/env python3
"""Isolated official company-master sync; fail closed, preserve last good snapshot."""
import datetime,json,pathlib,urllib.request,urllib.error,time,urllib.parse
ROOT=pathlib.Path(__file__).resolve().parent
SOURCES={"上市":"https://openapi.twse.com.tw/v1/opendata/t187ap03_L","上櫃":"https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"}
def first(row,*names):
    for k in names:
        v=row.get(k)
        if v is not None and str(v).strip():return str(v).strip()
    return ""
def main():
    result=[];counts={}
    for market,url in SOURCES.items():
        raw=None
        for attempt in range(1,4):
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; SectorRotationData/1.0)","Accept":"application/json","Accept-Language":"zh-TW,zh;q=0.9,en;q=0.8"})
            try:
                with urllib.request.urlopen(req,timeout=45) as response:
                    raw=response.read(12000001)
                break
            except urllib.error.HTTPError as exc:
                print("SOURCE_HTTP_ERROR",market,"attempt",attempt,"status",exc.code,"host",urllib.parse.urlparse(url).hostname,flush=True)
                if exc.code in (401,403,404):
                    raise RuntimeError("official source rejected request; existing snapshot preserved") from exc
                if attempt==3:raise
                time.sleep(attempt*3)
            except (urllib.error.URLError,TimeoutError) as exc:
                print("SOURCE_NETWORK_ERROR",market,"attempt",attempt,type(exc).__name__,flush=True)
                if attempt==3:raise
                time.sleep(attempt*3)
        if len(raw)>12000000:raise ValueError("oversize "+market)
        data=json.loads(raw.decode("utf-8-sig"))
        if not isinstance(data,list):raise ValueError("not array "+market)
        items=[]
        for x in data:
            if not isinstance(x,dict):continue
            code=first(x,"公司代號","股票代號","SecuritiesCompanyCode","Code")
            if not(code.isdigit() and len(code)==4):continue
            name=first(x,"公司簡稱","公司名稱","股票名稱","SecuritiesCompanyName","Name")
            if not name:continue
            industry=first(x,"產業別","產業類別","Industry","IndustryType") or "未分類"
            items.append({"id":code,"name":name,"industry":industry,"market":market})
        if len(items)<300:
            sample=data[0] if data else {}
            print("SOURCE_SCHEMA_DIAGNOSTIC",market,"rows",len(data),"keys",list(sample.keys()) if isinstance(sample,dict) else type(sample).__name__,"sample",str(sample)[:700],flush=True)
            raise ValueError("incomplete "+market+" "+str(len(items)))
        counts[market]=len(items);result.extend(items)
    ids=[x["id"] for x in result]
    if len(ids)!=len(set(ids)):raise ValueError("duplicate codes")
    if len(result)<1000:raise ValueError("incomplete market total")
    output=ROOT/"data"/"stocks.json";output.parent.mkdir(parents=True,exist_ok=True)
    payload={"updated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"market_counts":counts,"source_urls":SOURCES,"stocks":sorted(result,key=lambda x:x["id"])}
    tmp=output.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    tmp.replace(output)
    print("PASS",counts)
if __name__=="__main__":main()
