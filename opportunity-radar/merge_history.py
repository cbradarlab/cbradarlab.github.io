#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preserve prior opportunity history across small daily refresh windows.
Also removes near-duplicate same-company events and late local 'already opened' leads.
"""
from __future__ import annotations
import datetime as dt, json, re
from pathlib import Path
import update as core

ROOT=Path(__file__).resolve().parent
PREVIOUS=Path('/tmp/opportunity-events-before.json')
EVENTS=ROOT/'events.json'; STATUS=ROOT/'status.json'
HISTORY_DAYS=450
LATE_LOCAL=('啟用','落成','已完工','正式投產','投入營運','開幕')
TAINAN_DISTRICTS=('中西區','東區','南區','北區','安平區','安南區','永康區','歸仁區','新化區','左鎮區','玉井區','楠西區','南化區','仁德區','關廟區','龍崎區','官田區','麻豆區','佳里區','西港區','七股區','將軍區','學甲區','北門區','新營區','後壁區','白河區','東山區','六甲區','下營區','柳營區','鹽水區','善化區','大內區','山上區','新市區','安定區')

def company_core(s:str)->str:
    s=re.sub(r'(?:股份有限公司|有限公司|公司)$','',s or '')
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

def actionable(e):
    if e.get('local_source'):
        title=e.get('title','')
        if any(k in title for k in LATE_LOCAL):return False
    return True

def normalize(e):
    if e.get('city')=='台南':
        blob=' '.join([str(e.get('district','')),str(e.get('title','')),str(e.get('stage',''))])
        for d in TAINAN_DISTRICTS:
            if d in blob:
                e['district']=d; break
    return e

def merge():
    current=json.loads(EVENTS.read_text(encoding='utf-8'))
    previous=[]
    if PREVIOUS.exists():
        try:previous=json.loads(PREVIOUS.read_text(encoding='utf-8'))
        except Exception:previous=[]
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    pool=[]
    for e in current+previous:
        e=normalize(dict(e))
        if not actionable(e):continue
        d=date_of(e)
        if d and (today-d).days>HISTORY_DAYS:continue
        if not e.get('company'):continue
        pool.append(e)
    # Prefer manually verified, richer explicit evidence, then official central sources.
    pool.sort(key=lambda e:(priority(e),e.get('date','')),reverse=True)
    kept=[]
    for e in pool:
        if any(near_duplicate(e,x) for x in kept):continue
        if e.get('id') and any(e.get('id')==x.get('id') for x in kept):continue
        kept.append(e)
    kept.sort(key=lambda e:(e.get('date',''),e.get('score',0)),reverse=True)
    EVENTS.write_text(json.dumps(kept,ensure_ascii=False,indent=2),encoding='utf-8')
    status=json.loads(STATUS.read_text(encoding='utf-8'))
    status['total_event_count']=len(kept)
    status['unique_company_count']=len({company_core(e.get('company','')) for e in kept if company_core(e.get('company',''))})
    status['total_auto_event_count']=sum(1 for e in kept if e.get('auto'))
    status['total_manual_event_count']=sum(1 for e in kept if not e.get('auto'))
    status['tainan_local_event_count']=sum(1 for e in kept if e.get('local_source'))
    status['history_preservation']='ON_450D'
    status['timeline_dedupe']='SAME_COMPANY_WITHIN_3D'
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    core.render_topics(kept,now.isoformat(timespec='minutes'))
    print(json.dumps({'events':len(kept),'unique_companies':status['unique_company_count'],'auto':status['total_auto_event_count'],'local':status['tainan_local_event_count']},ensure_ascii=False))

if __name__=='__main__':merge()
