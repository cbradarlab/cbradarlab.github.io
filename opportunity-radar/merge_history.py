#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preserve opportunity history, normalize company names, and purge false local leads."""
from __future__ import annotations
import datetime as dt, json, re
from pathlib import Path
import update as core

ROOT=Path(__file__).resolve().parent
PREVIOUS=Path('/tmp/opportunity-events-before.json')
EVENTS=ROOT/'events.json'; STATUS=ROOT/'status.json'; HISTORY_DAYS=450
LATE_LOCAL=('啟用','落成','已完工','正式投產','投入營運','開幕')
BAD_LOCAL_TOKENS=('方案','基地','園區','供應鏈','能源管理','投資行動','加速投資','公開案件','資料來源','招商','工業區','科學園區','驗證基地','製造基地','市政府','經發局','經濟發展局','行政院','經濟部')
BAD_LOCAL_EXACT=('能源管理','先進製造基地','先進設備材料驗證基地','先進設備與材料驗證基地','中小企業方案','中小企業加速投資行動方案','根留台灣企業加速投資行動方案','根留臺灣企業加速投資行動方案')
BAD_ENDINGS=('擴大','長期','初期','一期','二期','公開案件')
TAINAN_DISTRICTS=('中西區','東區','南區','北區','安平區','安南區','永康區','歸仁區','新化區','左鎮區','玉井區','楠西區','南化區','仁德區','關廟區','龍崎區','官田區','麻豆區','佳里區','西港區','七股區','將軍區','學甲區','北門區','新營區','後壁區','白河區','東山區','六甲區','下營區','柳營區','鹽水區','善化區','大內區','山上區','新市區','安定區')

def normalize_company_name(s:str)->str:
    s=re.sub(r'\s+','',str(s or '')).strip('「」『』()（）,，:：')
    # Transitional cleanup for parser phrases already saved in history.
    for prefix in ('公開案件為','案件為'):
        if s.startswith(prefix):s=s[len(prefix):]
    if '係由' in s:s=s.split('係由',1)[0]
    # InvestTaiwan prose often starts with "公司名長期..." / "公司名初期...".
    s=re.sub(r'(長期|初期)$','',s)
    return s.strip('「」『』()（）,，:：')

def company_core(s:str)->str:
    s=normalize_company_name(s)
    s=re.sub(r'(?:股份有限公司|有限公司|公司)$','',s)
    s=re.sub(r'(?:企業|工業|科技|實業)$','',s)
    return re.sub(r'[^A-Za-z0-9\u4e00-\u9fff]','',s).lower()

def date_of(e):
    try:return dt.date.fromisoformat(e.get('date',''))
    except Exception:return None

def same_company(a,b):
    x,y=company_core(a.get('company','')),company_core(b.get('company',''))
    if not x or not y:return False
    return x==y or (min(len(x),len(y))>=2 and (x.startswith(y) or y.startswith(x)))

def near_duplicate(a,b):
    if not same_company(a,b):return False
    da,db=date_of(a),date_of(b)
    return bool(da and db and abs((da-db).days)<=3)

def priority(e):
    manual=1 if not e.get('auto') else 0
    explicit=len(e.get('explicit') or [])
    source=2 if '投資臺灣' in (e.get('source_type') or '') else (1 if e.get('local_source') else 0)
    return (manual,explicit,source,e.get('score',0))

def valid_local_company(e):
    if not e.get('local_source'):return True
    s=normalize_company_name(e.get('company',''))
    if not (2<=len(s)<=28):return False
    if s in BAD_LOCAL_EXACT:return False
    if any(x in s for x in BAD_LOCAL_TOKENS):return False
    if any(x in s for x in ('、','，','。','；')):return False
    if '由' in s and not s.endswith(('股份有限公司','有限公司')):return False
    if any(s.endswith(x) for x in BAD_ENDINGS):return False
    # Local leads must be recognizable businesses, not generic noun phrases.
    generic=('設備','材料驗證','製造','投資','管理','產業','行動')
    if s in generic:return False
    return True

def actionable(e):
    if not valid_local_company(e):return False
    if e.get('local_source') and any(k in e.get('title','') for k in LATE_LOCAL):return False
    return True

def normalize(e):
    e['company']=normalize_company_name(e.get('company',''))
    if e.get('city')=='台南':
        blob=' '.join([str(e.get('district','')),str(e.get('title','')),str(e.get('stage',''))])
        for d in TAINAN_DISTRICTS:
            if d in blob:e['district']=d;break
    return e

def merge():
    current=json.loads(EVENTS.read_text(encoding='utf-8')); previous=[]
    if PREVIOUS.exists():
        try:previous=json.loads(PREVIOUS.read_text(encoding='utf-8'))
        except Exception:previous=[]
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date();pool=[]
    for raw in current+previous:
        e=normalize(dict(raw))
        if not actionable(e):continue
        d=date_of(e)
        if d and (today-d).days>HISTORY_DAYS:continue
        if not e.get('company'):continue
        pool.append(e)
    pool.sort(key=lambda e:(priority(e),e.get('date','')),reverse=True);kept=[]
    for e in pool:
        if any(near_duplicate(e,x) for x in kept):continue
        if e.get('id') and any(e.get('id')==x.get('id') for x in kept):continue
        kept.append(e)
    kept.sort(key=lambda e:(e.get('date',''),e.get('score',0)),reverse=True)
    EVENTS.write_text(json.dumps(kept,ensure_ascii=False,indent=2),encoding='utf-8')
    status=json.loads(STATUS.read_text(encoding='utf-8'))
    status['total_event_count']=len(kept);status['unique_company_count']=len({company_core(e.get('company','')) for e in kept if company_core(e.get('company',''))})
    status['total_auto_event_count']=sum(1 for e in kept if e.get('auto'));status['total_manual_event_count']=sum(1 for e in kept if not e.get('auto'))
    status['local_event_count']=sum(1 for e in kept if e.get('local_source'))
    status['tainan_local_event_count']=sum(1 for e in kept if e.get('local_source') and e.get('region_source') not in ('kaohsiung','taichung') and e.get('city')=='台南')
    status['kaohsiung_local_event_count']=sum(1 for e in kept if e.get('region_source')=='kaohsiung')
    status['taichung_local_event_count']=sum(1 for e in kept if e.get('region_source')=='taichung')
    status['history_preservation']='ON_450D';status['timeline_dedupe']='SAME_COMPANY_WITHIN_3D';status['company_name_cleanup']='STRICT_LOCAL_PLUS_CENTRAL_SUFFIX_NORMALIZATION'
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)));core.render_topics(kept,now.isoformat(timespec='minutes'))
    print(json.dumps({'events':len(kept),'unique_companies':status['unique_company_count'],'auto':status['total_auto_event_count'],'local':status['local_event_count'],'kaohsiung':status['kaohsiung_local_event_count'],'taichung':status['taichung_local_event_count']},ensure_ascii=False))

if __name__=='__main__':merge()
