#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Classify strict demand-pull expansion events for Opportunity Radar.

Definition: official evidence must connect real market/customer/order demand growth
with added capacity, a new/expanded factory, a production line, equipment capacity,
or service capacity. This is an observation-priority context, never a buy signal.

Safety rules:
- research-validated historical events are keyed by exact stock_code + event date;
- new automatic events require an official-source causal match;
- new automatic events must also have been listed on/before the event date;
- no later-listing backfill and no name-only stock guessing.
"""
from __future__ import annotations
import datetime as dt
import json
import re
from pathlib import Path

import update as updater
import enrich_official_contacts as contacts

ROOT = Path(__file__).resolve().parent
EVENTS = ROOT / 'events.json'
STATUS = ROOT / 'status.json'

# Research ledger: exact event date + stock code. A- is retained as a boundary case.
# 6182/2026-10-08 qualifies by event definition but is forward-only/right-censored
# for performance validation as of the sealed research checkpoint.
KNOWN = {
    ('8147','2024-06-12'):('A','RESEARCH_VALIDATED_V1'),
    ('2504','2024-09-13'):('A','RESEARCH_VALIDATED_V1'),
    ('2369','2026-05-29'):('A','RESEARCH_VALIDATED_V1'),
    ('6509','2026-03-19'):('A','RESEARCH_VALIDATED_V1'),
    ('3580','2024-04-25'):('A','RESEARCH_VALIDATED_V1'),
    ('2460','2025-01-10'):('A','RESEARCH_VALIDATED_V1'),
    ('4721','2025-12-19'):('A','RESEARCH_VALIDATED_V1'),
    ('6658','2024-05-10'):('A','RESEARCH_VALIDATED_V1'),
    ('8028','2024-11-29'):('A','RESEARCH_VALIDATED_V1'),
    ('6277','2024-12-13'):('A','RESEARCH_VALIDATED_V1'),
    ('3645','2025-01-17'):('A','RESEARCH_VALIDATED_V1'),
    ('8028','2025-12-04'):('A','RESEARCH_VALIDATED_V1'),
    ('3705','2024-09-20'):('A','RESEARCH_VALIDATED_V1'),
    ('8210','2024-10-16'):('A','RESEARCH_VALIDATED_V1'),
    ('2368','2024-05-30'):('A','RESEARCH_VALIDATED_V1'),
    ('2303','2026-07-29'):('A','RESEARCH_VALIDATED_V1'),
    ('2330','2024-04-18'):('A','RESEARCH_VALIDATED_V1'),
    ('6515','2026-02-25'):('A','RESEARCH_VALIDATED_V1'),
    ('6239','2025-11-14'):('A','RESEARCH_VALIDATED_V1'),
    ('6510','2025-12-03'):('A','RESEARCH_VALIDATED_V1'),
    ('6829','2024-05-03'):('A','RESEARCH_VALIDATED_V1'),
    ('2356','2026-07-28'):('A','RESEARCH_VALIDATED_V1'),
    ('3264','2026-07-31'):('A','RESEARCH_VALIDATED_V1'),
    ('3516','2026-08-21'):('A','RESEARCH_VALIDATED_V1'),
    ('4545','2026-06-26'):('A','RESEARCH_VALIDATED_V1'),
    ('8091','2025-12-26'):('A','RESEARCH_VALIDATED_V1'),
    ('3081','2026-08-26'):('A','RESEARCH_VALIDATED_V1'),
    ('2449','2024-04-26'):('A','RESEARCH_VALIDATED_V1'),
    ('8155','2024-11-07'):('A','RESEARCH_VALIDATED_V1'),
    ('9930','2026-07-31'):('A','RESEARCH_VALIDATED_V1'),
    ('6664','2024-09-19'):('A-','RESEARCH_BOUNDARY_A_MINUS_V1'),
    ('6182','2026-10-08'):('FWD','RESEARCH_DEFINITION_FORWARD_ONLY_V1'),
}

DEMAND_TERMS = (
    '市場需求','客戶需求','訂單需求','訂單增加','訂單成長','訂單成長需求','訂單強勁',
    '接單增加','接單成長','接單及產能需求增加','產能需求增加','未來訂單需求',
    '需求增加','需求成長','需求旺盛','需求強勁','需求持續成長','市場成長需求',
    '因應訂單','滿足訂單','因應市場需求','因應客戶需求','滿足客戶需求','滿足市場需求',
    'ai需求','ai伺服器需求','hpc需求','高效能運算需求'
)
ACTION_TERMS = (
    '擴充產能','擴增產能','增加產能','提升產能','擴大產能','新增產能','新產能',
    '新增產線','擴增產線','擴充產線','擴建產線','建置產線','增設產線',
    '新廠','擴廠','擴建廠房','興建廠房','興建新廠','建置新廠','新建廠房',
    '擴充生產空間','增加生產空間','新增生產空間','擴充量能','新增量能','擴充服務量能',
    '增購設備','添購設備','擴充設備','新增設備'
)
NEGATIVE_TERMS = ('暫緩擴產','取消擴產','停止擴產','無擴產計畫','沒有擴產計畫','尚無擴產計畫')
MAX_TERM_DISTANCE = 180


def ntext(s):
    return re.sub(r'\s+','',str(s or '')).lower()


def first_pos(text, terms):
    hits=[]
    for term in terms:
        p=text.find(ntext(term))
        if p >= 0:hits.append((p,term))
    return min(hits, default=None)


def causal_match(text):
    t=ntext(text)
    if not t or any(ntext(x) in t for x in NEGATIVE_TERMS):return None
    demands=[(t.find(ntext(x)),x) for x in DEMAND_TERMS if t.find(ntext(x))>=0]
    actions=[(t.find(ntext(x)),x) for x in ACTION_TERMS if t.find(ntext(x))>=0]
    if not demands or not actions:return None
    best=min(((abs(dp-ap),d,a) for dp,d in demands for ap,a in actions), key=lambda x:x[0])
    if best[0] > MAX_TERM_DISTANCE:return None
    return {'demand_term':best[1],'action_term':best[2],'distance':best[0]}


def parse_listing_date(v):
    s=str(v or '').strip()
    if not s:return ''
    nums=[int(x) for x in re.findall(r'\d+',s)]
    try:
        if len(nums)>=3:
            y,m,d=nums[:3]
            if y < 1911:y += 1911
            return f'{y:04d}-{m:02d}-{d:02d}'
        digits=re.sub(r'\D','',s)
        if len(digits)==8:return f'{digits[:4]}-{digits[4:6]}-{digits[6:8]}'
        if len(digits)==7:
            y=int(digits[:3])+1911
            return f'{y:04d}-{digits[3:5]}-{digits[5:7]}'
    except Exception:pass
    return ''


def listing_field(row):
    candidates=('上市日期','上櫃日期','掛牌日期','ListingDate','DateOfListing','DateofListing','ListDate')
    for k in candidates:
        if k in row and str(row.get(k) or '').strip():return parse_listing_date(row.get(k))
    for k,v in row.items():
        lk=str(k).lower()
        if ('上市日期' in str(k) or '上櫃日期' in str(k) or ('list' in lk and 'date' in lk)) and str(v or '').strip():
            d=parse_listing_date(v)
            if d:return d
    return ''


def official_listing_dates():
    out={};stats={};failures={}
    for market in ('TWSE','TPEx'):
        rows,url,errs=contacts.load_market(market);stats[market]=len(rows)
        if not rows:
            failures[market]=errs;continue
        for r in rows:
            code=contacts.field(r,'code')
            if not code:continue
            d=listing_field(r)
            if d:out[(market,str(code).strip())]=d
    return out,stats,failures


def source_segment(event, cache):
    url=str(event.get('source') or '').strip()
    if not url:return ''
    if url not in cache:
        try:
            raw=updater.fetch(url)
            cache[url]={'raw':raw,'text':updater.plain_text(raw),'paragraphs':updater.detail_paragraphs(raw) if 'investtaiwan.nat.gov.tw' in url else []}
        except Exception as e:
            cache[url]={'error':f'{type(e).__name__}:{str(e)[:120]}'}
    obj=cache[url]
    if obj.get('error'):return ''
    company=contacts.core_name(event.get('company'))
    if obj.get('paragraphs'):
        for comp,seg in obj['paragraphs']:
            if contacts.core_name(comp)==company:return seg
        return ''  # aggregate page: do not borrow another company's paragraph
    text=obj.get('text','')
    if company and company in contacts.core_name(text):return text
    # Regional pages may use the short company name with punctuation/spacing differences.
    simple=ntext(event.get('company'))
    return text if simple and simple in ntext(text) else ''


def main():
    events=json.loads(EVENTS.read_text(encoding='utf-8'))
    status=json.loads(STATUS.read_text(encoding='utf-8'))
    listing_dates,market_rows,listing_failures=official_listing_dates()
    cache={};verified=0;strict_a=0;boundary=0;forward=0;auto_count=0;pending_listing=0
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='seconds')

    for e in events:
        for k in ('demand_pull','demand_pull_grade','demand_pull_basis','demand_pull_demand_term','demand_pull_action_term','demand_pull_checked_at','listing_date_at_check'):
            e.pop(k,None)
        code=str(e.get('stock_code') or '').strip();date=str(e.get('date') or '').strip();market=str(e.get('market') or '').strip()
        if not code or not market:continue
        listing_date=listing_dates.get((market,code),'')
        if listing_date:e['listing_date_at_check']=listing_date

        known=KNOWN.get((code,date))
        if known:
            grade,basis=known
            e['demand_pull']=True;e['demand_pull_grade']=grade;e['demand_pull_basis']=basis;e['demand_pull_checked_at']=now
            verified+=1
            if grade=='A':strict_a+=1
            elif grade=='A-':boundary+=1
            elif grade=='FWD':forward+=1
            continue

        seg=source_segment(e,cache)
        match=causal_match(seg)
        if not match:continue
        if not listing_date:
            pending_listing+=1;continue
        if listing_date > date:
            continue  # no later-listing backfill
        e['demand_pull']=True;e['demand_pull_grade']='AUTO';e['demand_pull_basis']='AUTO_OFFICIAL_CAUSAL_V1';e['demand_pull_checked_at']=now
        e['demand_pull_demand_term']=match['demand_term'];e['demand_pull_action_term']=match['action_term']
        verified+=1;auto_count+=1

    EVENTS.write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
    status['demand_pull_classifier']='DEMAND_PULL_STRICT_V1'
    status['demand_pull_verified_events']=verified
    status['demand_pull_research_A_events']=strict_a
    status['demand_pull_boundary_A_minus_events']=boundary
    status['demand_pull_forward_only_events']=forward
    status['demand_pull_auto_official_events']=auto_count
    status['demand_pull_pending_listing_date']=pending_listing
    status['demand_pull_listing_market_rows']=market_rows
    status['demand_pull_listing_failures']=listing_failures
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'verified':verified,'research_A':strict_a,'A_minus':boundary,'forward_only':forward,'auto_official':auto_count,'pending_listing':pending_listing,'listing_failures':listing_failures},ensure_ascii=False))

if __name__=='__main__':main()
