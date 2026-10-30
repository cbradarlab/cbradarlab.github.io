#!/usr/bin/env python3
"""Build official TWSE/TPEx listed/OTC stock industry registry from issuer master CSV.
Official primary industry only; thematic tags are separate and not inferred.
"""
import csv, io, json, re, sys, urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

URLS = {
    "TWSE": "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv",
    "TPEX": "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv",
}
OUTPUT = Path(__file__).parent / "data" / "official_stock_industries.csv"
REPORT = Path(__file__).parent / "data" / "official_stock_industries_report.json"

def get_rows(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 (compatible; sector-research/1.0)"})
    with urllib.request.urlopen(req, timeout=45) as res:
        raw = res.read()
    for enc in ("utf-8-sig", "cp950", "big5"):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("Cannot decode official CSV")
    reader = csv.DictReader(io.StringIO(txt))
    if not reader.fieldnames:
        raise ValueError("No official CSV header")
    reader.fieldnames = [x.strip().lstrip("\ufeff") for x in reader.fieldnames]
    required = {"公司代號", "公司簡稱", "產業別"}
    if not required.issubset(reader.fieldnames):
        raise ValueError("Official schema changed: " + str(reader.fieldnames[:12]))
    return list(reader)

def main():
    records = {}
    counts = {}
    for market,url in URLS.items():
        rows = get_rows(url)
        n = 0
        for row in rows:
            code = row["公司代號"].strip()
            if not re.fullmatch(r"[0-9]{4}",code):
                continue
            industry = row["產業別"].strip()
            name = row["公司簡稱"].strip()
            if not industry or not name:
                raise ValueError("Blank official industry/name for " + code)
            if code in records:
                raise ValueError("Duplicated stock across markets: " + code)
            records[code] = {"code":code,"name":name,"market":market,"official_industry":industry}
            n += 1
        counts[market] = n
        if n < 500:
            raise ValueError(f"Suspiciously low {market} coverage: {n}; refusing to publish")
    if len(records) < 1500:
        raise ValueError("Insufficient full-market coverage")
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    with OUTPUT.open("w",encoding="utf-8-sig",newline="") as f:
        w = csv.DictWriter(f,fieldnames=["code","name","market","official_industry"])
        w.writeheader()
        w.writerows(records[k] for k in sorted(records))
    report = {"source":URLS,"generated_at_utc":datetime.now(timezone.utc).isoformat(),
              "stocks":len(records),"market_counts":counts,
              "industry_counts":dict(sorted(Counter(r["official_industry"] for r in records.values()).items())),
              "scope":"listed_and_otc_four_digit_stock_codes",
              "classification":"official_primary_industry_not_theme"}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))

if __name__=="__main__":
    main()
