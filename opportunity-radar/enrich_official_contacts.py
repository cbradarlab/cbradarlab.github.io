#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Best-effort official contact enrichment for TWSE/TPEx companies.

Only exact normalized company/full-name/abbreviation matches are accepted.
No guessed websites, phones or emails are written.
Existing enrichment is preserved when an official endpoint is temporarily unavailable.
"""
from __future__ import annotations
import csv
import datetime as dt
import io
import json
import re
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
EVENTS=ROOT/'events.json'
STATUS=ROOT/'status.json'
UA='Mozilla/5.0 OpportunityRadar/1.0 (+https://cbradarlab.github.io/opportunity-radar/)'
TIMEOUT=20
SOURCES={
    'TWSE':[
        ('json','https://openapi.twse.com.tw/v1/opendata/t187ap03_L'),
        ('csv','https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'),
    ],
    'TPEx':[
        ('json','https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O'),
        ('csv','https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv'),
    ],
}


def clean(v):
    s=str(v or '').replace('\u3000',' ').strip()
    if s in ('-', '—', '－', 'N/A', 'NA', 'null', 'None'):return ''
    return re.sub(r'\s+',' ',s)


def core_name(v):
    s=clean(v)
    s=re.sub(r'[()（）「」『』,，:：\s]','',s)
    s=re.sub(r'(?:股份有限公司|有限公司|公司)$','',s)
    # Existing event names often omit these generic suffixes.
    s=re.sub(r'(?:企業|工業|科技|實業)$','',s)
    return re.sub(r'[^A-Za-z0-9\u4e00-\u9fff]','',s).lower()


def first(row,*candidates):
    # Exact keys first, then conservative semantic key matching.
    for k in candidates:
        if k in row and clean(row.get(k)):return clean(row.get(k))
    lowered={str(k).lower():k for k in row}
    for wanted in candidates:
        w=str(wanted).lower()
        if w in lowered and clean(row.get(lowered[w])):return clean(row.get(lowered[w]))
    return ''


def field(row,kind):
    if kind=='code':return first(row,'公司代號','SecuritiesCompanyCode','Code')
    if kind=='name':return first(row,'公司名稱','CompanyName')
    if kind=='abbr':return first(row,'公司簡稱','CompanyAbbreviation')
    if kind=='phone':return first(row,'總機電話','Telephone','Phone','CompanyTelephone')
    if kind=='email':return first(row,'電子郵件信箱','EmailAddress','Email','EMail')
    if kind=='web':return first(row,'網址','WebAddress','Website','WebSite')
    if kind=='address':return first(row,'住址','Address','CompanyAddress')
    return ''


def fetch_bytes(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json,text/csv,text/plain,*/*'})
    with urllib.request.urlopen(req,timeout=TIMEOUT) as r:return r.read()


def parse_csv(raw):
    text=''
    for enc in ('utf-8-sig','utf-8','cp950'):
        try:text=raw.decode(enc);break
        except Exception:pass
    if not text:raise RuntimeError('csv_decode_failed')
    return list(csv.DictReader(io.StringIO(text)))


def load_market(market):
    errors=[]
    for kind,url in SOURCES[market]:
        try:
            raw=fetch_bytes(url)
            rows=json.loads(raw.decode('utf-8-sig')) if kind=='json' else parse_csv(raw)
            if isinstance(rows,dict):
                rows=rows.get('data') or rows.get('result') or rows.get('rows') or []
            if not isinstance(rows,list) or not rows:raise RuntimeError('empty_rows')
            usable=[r for r in rows if isinstance(r,dict) and field(r,'name')]
            if not usable:raise RuntimeError('no_company_name_field')
            return usable,url,errors
        except Exception as e:
            errors.append(f'{kind}:{type(e).__name__}:{str(e)[:120]}')
    return [],'',errors


def normalize_web(v):
    v=clean(v)
    if not v:return ''
    if v.startswith('//'):return 'https:'+v
    if not re.match(r'^https?://',v,re.I):return 'https://'+v.lstrip('/')
    return v


def build_index(rows,market,source_url):
    tmp={}
    for r in rows:
        code=field(r,'code');name=field(r,'name');abbr=field(r,'abbr')
        rec={
            'stock_code':code,
            'market':market,
            'official_company_name':name,
            'company_website':normalize_web(field(r,'web')),
            'company_phone':field(r,'phone'),
            'company_email':field(r,'email'),
            'company_address':field(r,'address'),
            'contact_source':source_url,
        }
        keys={core_name(name),core_name(abbr)}-{''}
        for k in keys:tmp.setdefault(k,[]).append(rec)
    # Ambiguous normalized names are deliberately dropped.
    return {k:v[0] for k,v in tmp.items() if len(v)==1}


def main():
    events=json.loads(EVENTS.read_text(encoding='utf-8'))
    status=json.loads(STATUS.read_text(encoding='utf-8'))
    indexes={};source_urls={};failures={};market_rows={}
    for market in ('TWSE','TPEx'):
        rows,url,errs=load_market(market)
        market_rows[market]=len(rows);source_urls[market]=url
        if rows:indexes[market]=build_index(rows,market,url)
        else:failures[market]=errs

    matched=0;with_route=0;by_market={'TWSE':0,'TPEx':0}
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='seconds')
    for e in events:
        key=core_name(e.get('company'))
        hit=None
        for market in ('TWSE','TPEx'):
            rec=indexes.get(market,{}).get(key)
            if rec:
                hit=rec;break
        if not hit:continue
        matched+=1;by_market[hit['market']]+=1
        for k,v in hit.items():
            if v:e[k]=v
        e['contact_verified_at']=now
        if hit.get('company_website') or hit.get('company_phone') or hit.get('company_email'):with_route+=1

    EVENTS.write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
    status['official_contact_enrichment']='TWSE_TPEX_EXACT_NAME_V1'
    status['official_contact_market_rows']=market_rows
    status['official_contact_matched_events']=matched
    status['official_contact_routed_events']=with_route
    status['official_contact_matched_by_market']=by_market
    status['official_contact_sources']=source_urls
    status['official_contact_failures']=failures
    warnings=[w for w in status.get('warnings',[]) if not str(w).startswith('OFFICIAL_CONTACT_')]
    for market in failures:warnings.append(f'OFFICIAL_CONTACT_{market}_UNAVAILABLE')
    status['warnings']=warnings
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'matched_events':matched,'routed_events':with_route,'by_market':by_market,'market_rows':market_rows,'failures':failures},ensure_ascii=False))

if __name__=='__main__':main()
