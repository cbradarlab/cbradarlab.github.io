#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Add high-confidence local-government opportunity signals from Kaohsiung and Taichung.
Official source pages only. Conservative company/event extraction: prefer fewer clean leads.
"""
from __future__ import annotations
import datetime as dt, html, json, os, re, urllib.parse
from pathlib import Path
import update as core
import augment_local as local

ROOT=Path(__file__).resolve().parent
EVENTS=ROOT/'events.json'; STATUS=ROOT/'status.json'

SOURCES={
    'kaohsiung':{
        'city':'高雄',
        'pages':int(os.environ.get('KAOHSIUNG_PAGES','4')),
        'max_articles':int(os.environ.get('KAOHSIUNG_MAX_ARTICLES','30')),
        'list':'https://invest.kcg.gov.tw/News.aspx?n=8CE973AC5F6EE514&sms=D7173346CB507235&PageSize=20&page={page}',
        'base':'https://invest.kcg.gov.tw/',
        'source_type':'高雄招商網｜產業新聞',
    },
    'taichung':{
        'city':'台中',
        'pages':int(os.environ.get('TAICHUNG_PAGES','4')),
        'max_articles':int(os.environ.get('TAICHUNG_MAX_ARTICLES','30')),
        'list':'https://www.economic.taichung.gov.tw/2590629/Lpsimplelist?PageSize=20&page={page}',
        'base':'https://www.economic.taichung.gov.tw/',
        'source_type':'臺中市經發局｜招商新聞',
    },
}

TITLE_KEYS=('投資','新廠','動土','擴廠','建廠','設廠','興建','擴產','加碼','產線','廠房','落地生產')
TITLE_REJECT=('說明會','論壇','招商會','招商說明','產業用地','標售','標租','徵才','就業博覽','全台每','六都','工廠投資破','成果發表','會展中心','轉運中心','遊客中心','捷運','社宅')
LATE_KEYS=('啟用','落成','完工','正式投產','投入營運','開幕')
GENERIC_REJECT=('市政府','經濟發展局','經發局','行政院','經濟部','科學園區','產業園區','工業區','事務所','供應鏈','招商團隊')
CORP_HINTS=('科技','材料','工業','企業','精密','電子','半導體','氣體','能源','光電','化學','機械','生技','實業','製造','電機','股份','公司','台積電','聯華林德','ASML')
LEGAL_RE=re.compile(r'([^\s，。；：：「」()（）]{2,36}?(?:股份有限公司|有限公司))')
QUOTE_RE=re.compile(r'[「『]([^」』]{2,24})[」』]')


def norm_title(s:str)->str:
    return re.sub(r'\s+',' ',core.plain_text(s)).strip()


def title_ok(title:str)->bool:
    return bool(title and any(k in title for k in TITLE_KEYS) and not any(k in title for k in TITLE_REJECT) and not any(k in title for k in LATE_KEYS))


def discover_links(name:str,cfg:dict):
    found=[]; pages_ok=0
    for page in range(1,cfg['pages']+1):
        try:raw=core.fetch(cfg['list'].format(page=page)); pages_ok+=1
        except Exception as e:
            print('WARN REGION_LIST',name,page,repr(e)); continue
        # Both sites expose ordinary anchors; accept detail-page patterns conservatively.
        for m in re.finditer(r'''<a[^>]+href=["']([^"']+)["'][^>]*>(.*?)</a>''',raw,re.I|re.S):
            href=html.unescape(m.group(1)); title=norm_title(m.group(2))
            if name=='kaohsiung':
                if 'News_Content.aspx' not in href or 's=' not in href:continue
            else:
                if not (re.search(r'/\d+/post(?:\?|$)',href) or 'News_Content.aspx' in href):continue
            if not title_ok(title):continue
            url=urllib.parse.urljoin(cfg['base'],href)
            item=(url,title)
            if item not in found:found.append(item)
            if len(found)>=cfg['max_articles']:return found,pages_ok
    return found,pages_ok


def pub_date(text:str)->str:
    # Gregorian pages (Taichung) first.
    pats=(r'(?:發布日期|刊登日期|日期)[：:\s]*(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})',)
    for pat in pats:
        m=re.search(pat,text)
        if m:return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    # ROC dates (Kaohsiung): data update date / publication date.
    m=re.search(r'(?:資料更新時間|上版日期|發布日期)[：:\s]*(\d{2,3})[-/.](\d{1,2})[-/.](\d{1,2})',text)
    if m:return f'{int(m.group(1))+1911:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    return core.extract_date(text,'')


def clean_company(s:str)->str:
    s=re.sub(r'\s+','',s or '').strip('「」『』()（）,，:：')
    for p in ('國內','全球','國際','半導體','AI','供應鏈'):
        if s.startswith(p) and len(s)>len(p)+2:s=s[len(p):]
    s=re.sub(r'^(?:大廠|業者|公司|企業)','',s)
    if any(x in s for x in GENERIC_REJECT):return ''
    if len(s)<2 or len(s)>36:return ''
    return s


def title_candidates(title:str):
    out=[]
    # Explicit visit wording is common in Taichung investment-care news.
    for m in re.finditer(r'訪(?:視)?([A-Za-z0-9\u4e00-\u9fff]{2,20})',title):
        x=clean_company(m.group(1))
        for stop in ('助攻','加速','布局','投資','擴產','擴廠','新廠','動土'):
            if stop in x:x=x.split(stop,1)[0]
        if x and any(h in x for h in CORP_HINTS):out.append(x)
    # Company usually immediately precedes a concrete action word in official headlines.
    for m in re.finditer(r'([A-Za-z0-9\u4e00-\u9fff]{2,18}?)(?=(?:砸|斥資|投資|擴產|擴廠|新廠|動土|於高雄|於台中|於臺中|中科設新廠))',title):
        x=clean_company(m.group(1))
        # Strip headline context after punctuation-like markers that regex cannot see.
        for marker in ('供應鏈','效應','發威','需求'):
            if marker in x:x=x.rsplit(marker,1)[-1]
        if x and any(h in x for h in CORP_HINTS):out.append(x)
    return list(dict.fromkeys(out))


def company_candidates(text:str,title:str):
    out=[]
    for m in LEGAL_RE.finditer(text):
        x=clean_company(m.group(1))
        if x:out.append(x)
    for m in QUOTE_RE.finditer(text):
        x=clean_company(m.group(1))
        if x and any(h in x for h in CORP_HINTS):out.append(x)
    out.extend(title_candidates(title))
    # Prefer shorter clean company forms over sentence fragments; dedupe by normalized core.
    best={}
    for x in out:
        c=local.company_core(x)
        if not c:continue
        old=best.get(c)
        if old is None or len(x)<len(old):best[c]=x
    return list(best.values())


def relevant_parts(lines,comp,title):
    core_name=re.sub(r'(?:股份有限公司|有限公司|公司)$','',comp)
    parts=[]
    for line in lines:
        if len(line)<25:continue
        if comp in line or (len(core_name)>=2 and core_name in line):parts.append(line)
    if not parts:parts=[title]
    return ' '.join(dict.fromkeys(parts))


def stage_of(text:str):
    if '動土' in text or '開工' in text:return '已動土/開工｜地方政府公開'
    if any(k in text for k in ('興建新廠','中科設新廠','新廠','建廠','設廠')):return '新廠/建廠投資｜地方政府公開'
    if any(k in text for k in ('擴廠','擴建','擴產','增加產線','新增產線','擴充產能')):return '擴廠/擴產｜地方政府公開'
    return '企業投資/產線升級｜地方政府公開'


def inferred_of(text:str):
    out=[]
    if any(k in text for k in ('動土','開工','興建新廠','新廠','建廠','中科設新廠','擴建廠房','廠房擴建','擴廠')):
        out+=['消防/弱電','冰水主機/空調']
    if '倉儲' in text:out+=['智慧倉儲']
    return list(dict.fromkeys(out))


def extract_events(name:str,cfg:dict,url:str,title:str):
    raw=core.fetch(url); lines=core.block_lines(raw); page=' '.join(lines)
    date=pub_date(page)
    if not date:return []
    if any(k in title for k in LATE_KEYS):return []
    companies=company_candidates(page,title); out=[]
    for comp in companies:
        text=relevant_parts(lines,comp,title)
        # A company mention is not enough; its own context must contain an investment/build signal.
        if not any(k in text+' '+title for k in TITLE_KEYS):continue
        needs=core.explicit_needs(text)
        inf=inferred_of(text+' '+title)
        if not needs and not inf and not any(k in text+' '+title for k in ('投資','擴產','擴充產能','增加產線','新增產線')):continue
        amt=core.amount_billion(text) or core.amount_billion(title)
        score=80 if needs else 72
        if any(k in text+' '+title for k in ('動土','開工')):score+=5
        if amt>=5:score+=3
        if amt>=20:score+=2
        out.append({
            'company':comp,'date':date,'city':cfg['city'],'district':local.district(text+' '+title),
            'amount':amt,'stage':stage_of(text+' '+title),'industry':'地方建廠/擴產早期訊號',
            'explicit':list(needs.keys()),'explicit_evidence':needs,'inferred':inf,
            'contact':'公司名稱已識別｜可再接公開公司聯絡資料','source':url,
            'source_type':cfg['source_type'],'score':min(95,score),'id':core.event_id(comp,date,url),
            'auto':True,'local_source':True,'region_source':name,'title':title
        })
    return out


def main():
    events=json.loads(EVENTS.read_text(encoding='utf-8'))
    status=json.loads(STATUS.read_text(encoding='utf-8'))
    all_added=[]; region_stats={}
    for name,cfg in SOURCES.items():
        links,pages_ok=discover_links(name,cfg); checked=0; failures=0; found=[]
        for url,title in links:
            try:found.extend(extract_events(name,cfg,url,title)); checked+=1
            except Exception as e:
                failures+=1; print('WARN REGION_ARTICLE',name,url,repr(e))
        added=[]
        for e in sorted(found,key=lambda x:(x.get('date',''),x.get('score',0)),reverse=True):
            if local.is_near_duplicate(e,events+all_added+added):continue
            if e.get('id') in {x.get('id') for x in events+all_added+added}:continue
            added.append(e)
        all_added.extend(added)
        region_stats[name]={'pages_checked':pages_ok,'candidate_articles':len(links),'articles_checked':checked,'article_failures':failures,'new_event_count':len(added)}
    merged=events+all_added; merged.sort(key=lambda e:(e.get('date',''),e.get('score',0)),reverse=True)
    EVENTS.write_text(json.dumps(merged,ensure_ascii=False,indent=2),encoding='utf-8')
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))); core.render_topics(merged,now.isoformat(timespec='minutes'))
    status['updated_at']=now.isoformat(timespec='seconds')
    status['regional_sources']='KAOHSIUNG_TAICHUNG_OFFICIAL'
    for name,st in region_stats.items():
        prefix='kaohsiung' if name=='kaohsiung' else 'taichung'
        for k,v in st.items():status[f'{prefix}_{k}']=v
    status['regional_local_new_event_count']=len(all_added)
    status['total_event_count']=len(merged)
    status['unique_company_count']=len({local.company_core(e.get('company','')) for e in merged if local.company_core(e.get('company',''))})
    warnings=[w for w in status.get('warnings',[]) if not str(w).startswith(('KAOHSIUNG_','TAICHUNG_'))]
    for name,st in region_stats.items():
        tag=name.upper()
        if st['article_failures']:warnings.append(f"{tag}_FAILURES={st['article_failures']}")
        if st['pages_checked']==0:warnings.append(f'{tag}_LIST_UNAVAILABLE')
    status['warnings']=warnings
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'regional_added':len(all_added),'regions':region_stats,'total':len(merged)},ensure_ascii=False))

if __name__=='__main__':main()
