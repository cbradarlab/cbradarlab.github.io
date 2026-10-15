#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Augment Opportunity Radar with high-confidence local-government early signals.
Current production lane: Tainan Economic Development Bureau latest news.
Supports a one-time deeper backfill while daily runs preserve prior local events.
"""
from __future__ import annotations
import datetime as dt, html, json, os, re, urllib.parse
from pathlib import Path
import update as core

ROOT=Path(__file__).resolve().parent
PREVIOUS=Path('/tmp/opportunity-events-before.json')
TAINAN_LIST='https://economic.tainan.gov.tw/News.aspx?PageSize=20&n=5140&page={page}&sms=9749'
TAINAN_BASE='https://economic.tainan.gov.tw/'
PAGES=int(os.environ.get('TAINAN_PAGES','4')); MAX_ARTICLES=int(os.environ.get('TAINAN_MAX_ARTICLES','30'))
TITLE_KEYS=('投資','新廠','動土','擴廠','建廠','設廠','落成','興建','擴產','加碼','擴大布局')
TITLE_REJECT=('說明會','論壇','產業用地','標售','標租','招商','座談','交流會')
BODY_KEYS=('投資','新廠','動土','擴廠','建廠','設廠','落成','興建','擴產','加碼','導入','設備')
REJECT=('臺南市政府','台南市政府','經濟發展局','投資臺灣事務所','行政院','經濟部')
COMPANY_RE=re.compile(r'([^\s，。；：：「」]{2,30}?(?:股份有限公司|有限公司))')
PREFIX_SPLITS=('總經理及','董事長及','負責人及','並安排','並邀請','以及','包括','包含')

def roc_pub_date(text:str):
    m=re.search(r'刊登日期[：:\s]*(\d{2,3})[-/.](\d{1,2})[-/.](\d{1,2})',text)
    if not m:return ''
    return f'{int(m.group(1))+1911:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'

def district(text:str):
    for m in re.finditer(r'([\u4e00-\u9fff]{1,4}區)',text):
        x=m.group(1)
        if x not in ('地區','園區','廠區','專區','區域','工業區'):return x
    return ''

def clean_context(text:str):
    return re.sub(r'(?:半導體|晶圓廠|客戶)[^，。；]{0,8}建廠(?:需求)?',' ',text)

def stage_of(text:str):
    text=clean_context(text)
    if '動土' in text:return '已動土｜地方政府公開'
    if '落成' in text or '完工' in text:return '已落成/完工｜地方政府公開'
    if any(k in text for k in ('興建新廠','新建廠房','新廠','建廠')):return '新廠/建廠投資｜地方政府公開'
    if any(k in text for k in ('擴建廠房','廠房擴建','擴廠','擴產')):return '擴廠/擴產｜地方政府公開'
    return '企業投資/產線升級｜地方政府公開'

def inferred_of(text:str):
    text=clean_context(text); out=[]
    if any(k in text for k in ('新廠','興建新廠','新建廠房','擴建廠房','廠房擴建','擴廠','動土')):out+=['消防/弱電','冰水主機/空調']
    if '倉儲' in text:out+=['智慧倉儲']
    return list(dict.fromkeys(out))

def company_core(s:str):
    s=re.sub(r'(?:股份有限公司|有限公司|公司)$','',s or '')
    s=re.sub(r'(?:企業|工業|科技|實業)$','',s)
    return re.sub(r'[^A-Za-z0-9\u4e00-\u9fff]','',s).lower()

def clean_company(s:str):
    s=s.strip('「」()（） ')
    for marker in PREFIX_SPLITS:
        if marker in s:s=s.rsplit(marker,1)[-1]
    s=re.sub(r'^(?:本週核准之|核准之|同樣規劃於|而|另|其中|至於|此外|並|及|由|邀請|安排)','',s)
    s=re.sub(r'^.{1,12}(?:總經理|董事長|負責人)', '', s)
    if '、' in s:return ''
    return s.strip('「」()（） ')

def discover_links():
    found=[]; pages_ok=0
    for page in range(1,PAGES+1):
        try:raw=core.fetch(TAINAN_LIST.format(page=page)); pages_ok+=1
        except Exception:continue
        for m in re.finditer(r'''<a[^>]+href=["']([^"']*News_Content\.aspx\?[^"']*s=\d+[^"']*)["'][^>]*>(.*?)</a>''',raw,re.I|re.S):
            title=core.plain_text(m.group(2))
            if not title or not any(k in title for k in TITLE_KEYS):continue
            if any(k in title for k in TITLE_REJECT):continue
            url=urllib.parse.urljoin(TAINAN_BASE,html.unescape(m.group(1)))
            item=(url,title)
            if item not in found:found.append(item)
            if len(found)>=MAX_ARTICLES:return found,pages_ok
    return found,pages_ok

def article_needs(text:str):
    needs=core.explicit_needs(text)
    if '智慧化產線' in text:
        needs.setdefault('自動化設備',[])
        if '智慧化產線' not in needs['自動化設備']:needs['自動化設備'].append('智慧化產線')
    return needs

def extract_events(url,title):
    raw=core.fetch(url); lines=core.block_lines(raw); page_text=' '.join(lines)
    date=roc_pub_date(page_text) or core.extract_date(page_text,'')
    if not date:return []
    segments={}
    for line in lines:
        if len(line)<45 or not any(k in line for k in BODY_KEYS):continue
        for m in COMPANY_RE.finditer(line):
            comp=clean_company(m.group(1))
            if len(comp)<4 or len(comp)>30 or any(x in comp for x in REJECT):continue
            segments.setdefault(comp,[]).append(line)
    out=[]
    for comp,parts in segments.items():
        text=' '.join(dict.fromkeys(parts)); needs=article_needs(text); inf=inferred_of(text+' '+title)
        if not needs and not inf:continue
        amt=core.amount_billion(text) or core.amount_billion(title)
        score=78 if needs else 70
        if '動土' in clean_context(text+' '+title):score+=5
        if amt>=5:score+=3
        if amt>=20:score+=2
        out.append({'company':comp,'date':date,'city':'台南','district':district(text+' '+title),'amount':amt,'stage':stage_of(text+' '+title),'industry':'地方建廠/擴產早期訊號','explicit':list(needs.keys()),'explicit_evidence':needs,'inferred':inf,'contact':'公司名稱已識別｜可再接公開公司聯絡資料','source':url,'source_type':'臺南市經發局｜投資/建廠新聞','score':min(94,score),'id':core.event_id(comp,date,url),'auto':True,'local_source':True,'title':title})
    return out

def is_near_duplicate(e,existing):
    c=company_core(e.get('company',''))
    if not c:return False
    try:d=dt.date.fromisoformat(e.get('date',''))
    except Exception:d=None
    for x in existing:
        xc=company_core(x.get('company',''))
        if not xc:continue
        same=(c==xc) or (min(len(c),len(xc))>=2 and (c.startswith(xc) or xc.startswith(c)))
        if not same:continue
        try:xd=dt.date.fromisoformat(x.get('date',''))
        except Exception:xd=None
        if d and xd and abs((d-xd).days)<=3:return True
    return False

def load_preserved(events):
    if not PREVIOUS.exists():return []
    try:old=json.loads(PREVIOUS.read_text(encoding='utf-8'))
    except Exception:return []
    kept=[]
    for e in old:
        if not e.get('local_source'):continue
        if e.get('id') in {x.get('id') for x in events+kept}:continue
        if is_near_duplicate(e,events+kept):continue
        kept.append(e)
    return kept

def main():
    events=json.loads((ROOT/'events.json').read_text(encoding='utf-8'))
    status=json.loads((ROOT/'status.json').read_text(encoding='utf-8'))
    preserved=load_preserved(events); events+=preserved
    links,pages_ok=discover_links(); local=[]; failures=0; checked=0
    for url,title in links:
        try:local.extend(extract_events(url,title)); checked+=1
        except Exception as e:
            failures+=1; print('WARN TAINAN',url,repr(e))
    added=[]
    for e in sorted(local,key=lambda x:(x.get('date',''),x.get('score',0)),reverse=True):
        if is_near_duplicate(e,events+added):continue
        if e.get('id') in {x.get('id') for x in events+added}:continue
        added.append(e)
    merged=events+added; merged.sort(key=lambda e:(e.get('date',''),e.get('score',0)),reverse=True)
    (ROOT/'events.json').write_text(json.dumps(merged,ensure_ascii=False,indent=2),encoding='utf-8')
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))); core.render_topics(merged,now.isoformat(timespec='minutes'))
    local_total=sum(1 for e in merged if e.get('local_source'))
    status.update({'source_status':'PASS_MULTI_SOURCE_LIVE_REFRESH_V2','updated_at':now.isoformat(timespec='seconds'),'buildlic_mode':'SHADOW_DISABLED_IN_DAILY_WORKFLOW','tainan_pages_checked':pages_ok,'tainan_candidate_articles':len(links),'tainan_articles_checked':checked,'tainan_article_failures':failures,'tainan_local_new_event_count':len(added),'tainan_local_preserved_event_count':len(preserved),'tainan_local_event_count':local_total,'total_event_count':len(merged),'unique_company_count':len({company_core(e.get('company','')) for e in merged if company_core(e.get('company',''))})})
    warnings=[w for w in status.get('warnings',[]) if not str(w).startswith(('TAINAN_','BUILDLIC_'))]
    if failures:warnings.append(f'TAINAN_FAILURES={failures}')
    status['warnings']=warnings
    (ROOT/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'tainan_new':len(added),'tainan_preserved':len(preserved),'tainan_total':local_total,'candidate_articles':len(links),'checked':checked,'failures':failures,'total':len(merged)},ensure_ascii=False))

if __name__=='__main__':main()
