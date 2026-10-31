#!/usr/bin/env python3
"""Validate sector membership outputs before publishing. No production player changes."""
import csv, json
from collections import Counter
from pathlib import Path
P=Path(__file__).resolve().parent/"data"
def load(name):
    with (P/name).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def main():
    official=load("official_stock_industries.csv")
    mapped=load("stock_panel_memberships.csv")
    review=load("stock_panel_review.csv")
    taxonomy=json.loads((P/"sector_taxonomy.json").read_text(encoding="utf-8"))
    report=json.loads((P/"stock_panel_report.json").read_text(encoding="utf-8"))
    universe={x["code"]:x for x in official}
    assert len(universe)==len(official)>=1500,"duplicate or missing official stocks"
    assert len(taxonomy["industry_chain"])==len(set(taxonomy["industry_chain"]))==30
    assert len(taxonomy["concepts"])==len(set(taxonomy["concepts"]))==30
    industries=[x for x in mapped if x["kind"]=="industry_chain"]
    concepts=[x for x in mapped if x["kind"]=="concept"]
    codes=[x["code"] for x in industries]
    review_codes=[x["code"] for x in review]
    assert len(codes)==len(set(codes)),"duplicate industry assignments"
    assert not (set(codes)&set(review_codes)),"review and mapped overlap"
    assert set(codes)|set(review_codes)==set(universe),"unaccounted official stock"
    assert all(x["panel"] in taxonomy["industry_chain"] for x in industries)
    assert all(x["panel"] in taxonomy["concepts"] and x["review_status"]=="verified" and x["source"] for x in concepts)
    assert report["official_stocks"]==len(official)
    assert report["industry_mapped"]==len(industries)
    assert report["industry_review"]==len(review)
    assert report["concept_mapped"]==len(concepts)
    print(json.dumps({"result":"PASS","official":len(official),"industry":len(industries),"review":len(review),"concept":len(concepts)},ensure_ascii=False))
if __name__=="__main__":main()
