#!/usr/bin/env python3
"""Derive stock-to-panel membership without inventing thematic associations.

Official market classifications are primary evidence. Each stock is assigned at
most one of the 30 research industry panels; unmatched official industries stay
in a review file, not in a fabricated 'other' bucket. Concept panels use only
explicit reviewed stock membership rows.
"""
import csv, json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OFFICIAL = DATA / "official_stock_industries.csv"
TAXONOMY = DATA / "sector_taxonomy.json"
OVERRIDES = DATA / "reviewed_stock_themes.csv"
OUT = DATA / "stock_panel_memberships.csv"
UNMATCHED = DATA / "stock_panel_review.csv"
REPORT = DATA / "stock_panel_report.json"

# Official industry labels and codes; map only where sector meaning is clear.
# Numeric codes are TWSE/TPEx industry codes, not inferred concept tags.
INDUSTRY_CODE = {
    "01":"水泥", "02":"食品", "03":"石化及塑橡膠", "04":"紡織",
    "05":"電機機械", "09":"造紙", "10":"鋼鐵", "11":"石化及塑橡膠",
    "12":"汽車", "14":"建材營造", "15":"交通運輸及航運",
    "17":"金融", "18":"貿易百貨", "21":"石化及塑橡膠",
    "23":"油電燃氣", "24":"半導體", "25":"電腦及週邊設備",
    "27":"通信網路", "28":"電子零組件", "30":"軟體服務",
    "34":"電子商務", "36":"雲端運算",
}
INDUSTRY_LABEL = {
    "水泥工業":"水泥","食品工業":"食品","塑膠工業":"石化及塑橡膠",
    "紡織纖維":"紡織","電機機械":"電機機械","造紙工業":"造紙",
    "鋼鐵工業":"鋼鐵","橡膠工業":"石化及塑橡膠",
    "汽車工業":"汽車","建材營造":"建材營造","航運業":"交通運輸及航運",
    "金融保險":"金融","貿易百貨":"貿易百貨","化學工業":"石化及塑橡膠",
    "油電燃氣業":"油電燃氣","半導體業":"半導體",
    "電腦及週邊設備業":"電腦及週邊設備","通信網路業":"通信網路",
    "電子零組件業":"電子零組件","資訊服務業":"軟體服務",
    "電子商務":"電子商務","數位雲端":"雲端運算",
}
def rows(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def main():
    taxonomy=json.loads(TAXONOMY.read_text(encoding="utf-8"))
    panels=set(taxonomy["industry_chain"])
    concepts=set(taxonomy["concepts"])
    if len(panels)!=30 or len(concepts)!=30:
        raise ValueError("Expected exactly 30+30 panels")
    if not OFFICIAL.exists():
        raise SystemExit("Official stock registry not available; run build_official_industries.py first")
    official=rows(OFFICIAL)
    if len(official)<1500:
        raise ValueError("Official stock registry coverage below 1500")
    output=[]; review=[]; seen=set(); stats=Counter()
    for stock in official:
        code=stock["code"].strip()
        if code in seen: raise ValueError("Duplicate official code "+code)
        seen.add(code)
        raw=stock["official_industry"].strip()
        panel=INDUSTRY_CODE.get(raw.zfill(2)) if raw.isdigit() else INDUSTRY_LABEL.get(raw)
        if panel and panel not in panels: raise ValueError("Mapped panel absent from taxonomy: "+panel)
        if panel:
            output.append({"code":code,"name":stock["name"],"market":stock["market"],
                "kind":"industry_chain","panel":panel,"source":"official_industry:"+raw,
                "review_status":"official_mapping"})
            stats["industry_mapped"]+=1
        else:
            review.append({"code":code,"name":stock["name"],"market":stock["market"],
                "official_industry":raw,"reason":"No safe 30-panel mapping"})
            stats["industry_review"]+=1
    if OVERRIDES.exists():
        theme_seen=set()
        for x in rows(OVERRIDES):
            code=x["code"].strip(); panel=x["concept"].strip()
            if not code or not panel: continue
            if code not in seen: raise ValueError("Concept code absent from official universe: "+code)
            if panel not in concepts: raise ValueError("Unknown concept: "+panel)
            if x["review_status"].strip()!="verified" or not x["evidence_url"].strip():
                raise ValueError("Unverified theme membership: "+code+" / "+panel)
            key=(code,panel)
            if key in theme_seen: raise ValueError("Duplicate theme membership "+str(key))
            theme_seen.add(key)
            company=next(s for s in official if s["code"]==code)
            output.append({"code":code,"name":company["name"],"market":company["market"],
                "kind":"concept","panel":panel,"source":x["evidence_url"],
                "review_status":"verified"})
            stats["concept_mapped"]+=1
    DATA.mkdir(exist_ok=True)
    def write(path,header,items):
        with path.open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.DictWriter(f,fieldnames=header);w.writeheader();w.writerows(items)
    write(OUT,["code","name","market","kind","panel","source","review_status"],output)
    write(UNMATCHED,["code","name","market","official_industry","reason"],review)
    REPORT.write_text(json.dumps({"official_stocks":len(official),"panel_count":60,
        "industry_mapped":stats["industry_mapped"],"industry_review":stats["industry_review"],
        "concept_mapped":stats["concept_mapped"],
        "note":"Concepts are not automatically inferred from official industry; incomplete panels are expected."},
        ensure_ascii=False,indent=2),encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"))
if __name__=="__main__": main()
