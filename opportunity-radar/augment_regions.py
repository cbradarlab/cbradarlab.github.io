#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""High-confidence regional opportunity signals.
Rule: the headline identifies the commercial actor; article body only corroborates it.
Prefer fewer clean leads over inflated counts.
"""
from __future__ import annotations
import datetime as dt, html, json, os, re, urllib.parse
from pathlib import Path
import update as core
import augment_local as local

ROOT=Path(__file__).resolve().parent
EVENTS=ROOT/'events.json'; STATUS=ROOT/'status.json'
SOURCES={
 'kaohsiung':{'city':'高雄','pages':int(os.environ.get('KAOHSIUNG_PAGES','2')),'max_articles':int(os.environ.get('KAOHSIUNG_MAX_ARTICLES','12')),'list':'https://invest.kcg.gov.tw/News.aspx?n=8CE973AC5F6EE514&sms=D7173346CB507235&PageSize=20&page={page}','base':'https://invest.kcg.gov.tw/','source_type':'高雄招商網｜產業新聞'},
 'taichung':{'city':'台中','pages':int(os.environ.get('TAICHUNG_PAGES','2')),'max_articles':int(os.environ.get('TAICHUNG_MAX_ARTICLES','12')),'list':'https://www.economic.taichung.gov.tw/2590629/Lpsimplelist?PageSize=20&page={page}','base':'https://www.economic.taichung.gov.tw/','source_type':'臺中市經發局｜招商新聞'},
 'taoyuan':{'city':'桃園','pages':int(os.environ.get('TAOYUAN_PAGES','2')),'max_articles':int(os.environ.get('TAOYUAN_MAX_ARTICLES','12')),'list':'https://edb.tycg.gov.tw/News.aspx?PageSize=20&n=3749&page={page}&sms=9954','base':'https://edb.tycg.gov.tw/','source_type':'桃園市經發局｜最新消息'},
 'hsinchu':{'city':'新竹縣','pages':int(os.environ.get('HSINCHU_PAGES','2')),'max_articles':int(os.environ.get('HSINCHU_MAX_ARTICLES','12')),'list':'https://dda.hsinchu.gov.tw/News.aspx?PageSize=20&n=3386&page={page}&sms=8603','base':'https://dda.hsinchu.gov.tw/','source_type':'新竹縣政府數位發展處｜縣府新聞'}
}
TITLE_KEYS=('投資','新廠','動土','擴廠','建廠','設廠','興建','擴產','加碼','產線','廠房','進駐','落地生產','擴充產能')
TITLE_REJECT=('說明會','論壇','招商會','招商說明','產業用地','標售','標租','徵才','就業博覽','全台每','六都','工廠投資破','成果發表','會展中心','轉運中心','遊客中心','捷運','社宅','產業園區盛大動土','園區動土','SBIR','補助計畫','審查通過名單','商機媒合大會','設計展','博覽會')
LATE_KEYS=('啟用','落成','完工','正式投產','投入營運','開幕','揭牌')
BAD_NAME_TOKENS=('方案','基地','園區','供應鏈','能源管理','投資行動','加速投資','公開案件','資料來源','招商','工業區','科學園區','驗證基地','製造基地','市政府','縣政府','經發局','經濟發展局','行政院','經濟部')
ACTION_SUFFIX=('擴大','長期','初期','一期','二期','三廠','二廠','新廠','建廠','設廠','擴廠','擴產','投資')
LEGAL_RE=re.compile(r'([^\s，。；：：「」()（）]{2,40}?(?:股份有限公司|有限公司))')
QUOTE_RE=re.compile(r'[「『]([^」』]{2,24})[」』]')


def norm_title(s):return re.sub(r'\s+',' ',core.plain_text(s)).strip()
def company_core(s):return local.company_core(s)

def title_ok(title):
    return bool(title and any(k in title for k in TITLE_KEYS) and not any(k in title for k in TITLE_REJECT) and not any(k in title for k in LATE_KEYS))

def discover_links(name,cfg):
    found=[]; pages_ok=0
    for page in range(1,cfg['pages']+1):
        try:raw=core.fetch(cfg['list'].format(page=page)); pages_ok+=1
        except Exception as e:print('WARN REGION_LIST',name,page,repr(e));continue
        for m in re.finditer(r'''<a[^>]+href=["']([^"']+)["'][^>]*>(.*?)</a>''',raw,re.I|re.S):
            href=html.unescape(m.group(1)); title=norm_title(m.group(2))
            if name=='kaohsiung':
                if 'News_Content.aspx' not in href or 's=' not in href:continue
            elif name=='taichung':
                if not (re.search(r'/\d+/post(?:\?|$)',href) or 'News_Content.aspx' in href):continue
            else:
                if 'News_Content.aspx' not in href or 's=' not in href:continue
            if not title_ok(title):continue
            item=(urllib.parse.urljoin(cfg['base'],href),title)
            if item not in found:found.append(item)
            if len(found)>=cfg['max_articles']:return found,pages_ok
    return found,pages_ok

def pub_date(text):
    m=re.search(r'(?:發布日期|刊登日期|日期)[：:\s]*(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})',text)
    if m:return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    m=re.search(r'(?:資料更新時間|上版日期|發布日期)[：:\s]*(\d{2,3})[-/.](\d{1,2})[-/.](\d{1,2})',text)
    if m:return f'{int(m.group(1))+1911:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    return core.extract_date(text,'')

def clean_company(s):
    s=re.sub(r'\s+','',s or '').strip('「」『』()（）,，:：')
    s=re.sub(r'^\d+','',s)
    for marker in ('公開案件為','案件為','由','包括','包含','以及'):
        if marker in s:s=s.rsplit(marker,1)[-1]
    for marker in ('大廠','供應鏈'):
        if marker in s:s=s.rsplit(marker,1)[-1]
    for geo in ('高雄','台中','臺中','中科','橋頭','楠梓','仁武','桃園','平鎮','中壢','龜山','蘆竹','大園','觀音','新竹','竹縣','竹北','湖口','新豐','寶山','竹東'):
        pos=s.find(geo)
        if pos>=2:s=s[:pos]
    for suf in ACTION_SUFFIX:
        if s.endswith(suf) and len(s)>len(suf)+1:s=s[:-len(suf)]
    s=s.strip('「」『』()（）,，:：')
    if not (2<=len(s)<=24):return ''
    if any(x in s for x in BAD_NAME_TOKENS):return ''
    if any(x in s for x in ('、','，','。','；')):return ''
    return s

def title_candidates(title):
    t=re.sub(r'^\s*\d+\s*','',title)
    out=[]
    for m in re.finditer(r'([A-Za-z0-9\u4e00-\u9fff＋+\-]{2,28}?)(?=(?:砸|斥資|再投資|投資|擴產|擴廠|擴大投資|新廠|動土|進駐|於高雄|於台中|於臺中|於桃園|於新竹|中科設新廠|竹北設廠|湖口設廠))',t):
        x=clean_company(m.group(1))
        if x:out.append(x)
    m=re.match(r'([A-Za-z0-9\u4e00-\u9fff＋+\-]{2,18}?)(?=(?:百億|千億|\d+(?:\.\d+)?億|擴產|擴廠|投資|新廠|動土|進駐))',t)
    if m:
        x=clean_company(m.group(1));
        if x:out.append(x)
    return list(dict.fromkeys(out))

def corroborated_candidates(page,title):
    headline=title_candidates(title); out=[]
    legal=[]
    for m in LEGAL_RE.finditer(page):
        x=clean_company(m.group(1))
        if x:legal.append(x)
    quoted=[]
    for m in QUOTE_RE.finditer(page):
        x=clean_company(m.group(1))
        if x:quoted.append(x)
    title_core=company_core(title)
    for x in legal+quoted:
        c=company_core(x)
        if c and c in title_core:out.append(x)
        elif x.endswith(('股份有限公司','有限公司')):
            short=re.sub(r'(?:股份有限公司|有限公司)$','',x)
            short=re.sub(r'(?:企業|工業|科技|實業)$','',short)
            if len(short)>=2 and short in title:out.append(x)
    page_core=company_core(page)
    for x in headline:
        c=company_core(x)
        if c and len(c)>=2 and c in page_core:out.append(x)
    best={}
    for x in out:
        c=company_core(x)
        old=best.get(c)
        if old is None:best[c]=x;continue
        xlegal=x.endswith(('股份有限公司','有限公司')); olegal=old.endswith(('股份有限公司','有限公司'))
        if xlegal and not olegal:best[c]=x
        elif xlegal==olegal and len(x)<len(old):best[c]=x
    return list(best.values())

def relevant_parts(lines,comp,title):
    c=re.sub(r'(?:股份有限公司|有限公司|公司)$','',comp)
    parts=[line for line in lines if len(line)>=25 and (comp in line or (len(c)>=2 and c in line))]
    return ' '.join(dict.fromkeys(parts)) if parts else title

def stage_of(text):
    if '動土' in text or '開工' in text:return '已動土/開工｜地方政府公開'
    if any(k in text for k in ('興建新廠','中科設新廠','新廠','建廠','設廠','進駐')):return '新廠/建廠投資｜地方政府公開'
    if any(k in text for k in ('擴廠','擴建','擴產','增加產線','新增產線','擴充產能')):return '擴廠/擴產｜地方政府公開'
    return '企業投資/產線升級｜地方政府公開'

def inferred_of(text):
    out=[]
    if any(k in text for k in ('動土','開工','興建新廠','新廠','建廠','中科設新廠','擴建廠房','廠房擴建','擴廠')):out+=['消防/弱電','冰水主機/空調']
    if '倉儲' in text:out+=['智慧倉儲']
    return list(dict.fromkeys(out))

def extract_events(name,cfg,url,title):
    raw=core.fetch(url); lines=core.block_lines(raw); page=' '.join(lines); date=pub_date(page)
    if not date or any(k in title for k in LATE_KEYS):return []
    out=[]
    for comp in corroborated_candidates(page,title):
        text=relevant_parts(lines,comp,title); blob=text+' '+title
        if not any(k in blob for k in TITLE_KEYS):continue
        needs=core.explicit_needs(text); inf=inferred_of(blob)
        if not needs and not inf and not any(k in blob for k in ('投資','擴產','擴充產能','增加產線','新增產線','進駐')):continue
        amt=core.amount_billion(text) or core.amount_billion(title); score=80 if needs else 72
        if any(k in blob for k in ('動土','開工')):score+=5
        if amt>=5:score+=3
        if amt>=20:score+=2
        out.append({'company':comp,'date':date,'city':cfg['city'],'district':local.district(blob),'amount':amt,'stage':stage_of(blob),'industry':'地方建廠/擴產早期訊號','explicit':list(needs.keys()),'explicit_evidence':needs,'inferred':inf,'contact':'公司名稱已識別｜可再接公開公司聯絡資料','source':url,'source_type':cfg['source_type'],'score':min(95,score),'id':core.event_id(comp,date,url),'auto':True,'local_source':True,'region_source':name,'title':title})
    return out

def main():
    events=json.loads(EVENTS.read_text(encoding='utf-8')); status=json.loads(STATUS.read_text(encoding='utf-8'))
    all_added=[]; stats={}
    for name,cfg in SOURCES.items():
        links,pages_ok=discover_links(name,cfg); checked=0; failures=0; found=[]
        for url,title in links:
            try:found.extend(extract_events(name,cfg,url,title));checked+=1
            except Exception as e:failures+=1;print('WARN REGION_ARTICLE',name,url,repr(e))
        added=[]
        for e in sorted(found,key=lambda x:(x.get('date',''),x.get('score',0)),reverse=True):
            if local.is_near_duplicate(e,events+all_added+added):continue
            if e.get('id') in {x.get('id') for x in events+all_added+added}:continue
            added.append(e)
        all_added.extend(added);stats[name]={'pages_checked':pages_ok,'candidate_articles':len(links),'articles_checked':checked,'article_failures':failures,'new_event_count':len(added)}
    merged=events+all_added;merged.sort(key=lambda e:(e.get('date',''),e.get('score',0)),reverse=True);EVENTS.write_text(json.dumps(merged,ensure_ascii=False,indent=2),encoding='utf-8')
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)));core.render_topics(merged,now.isoformat(timespec='minutes'));status['updated_at']=now.isoformat(timespec='seconds');status['regional_sources']='KAOHSIUNG_TAICHUNG_TAOYUAN_HSINCHU_OFFICIAL'
    for name,st in stats.items():
        for k,v in st.items():status[f'{name}_{k}']=v
    status['regional_local_new_event_count']=len(all_added);status['total_event_count']=len(merged);status['unique_company_count']=len({company_core(e.get('company','')) for e in merged if company_core(e.get('company',''))})
    warnings=[w for w in status.get('warnings',[]) if not str(w).startswith(('KAOHSIUNG_','TAICHUNG_','TAOYUAN_','HSINCHU_'))]
    for name,st in stats.items():
        if st['article_failures']:warnings.append(f"{name.upper()}_FAILURES={st['article_failures']}")
        if st['pages_checked']==0:warnings.append(f'{name.upper()}_LIST_UNAVAILABLE')
    status['warnings']=warnings;STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'regional_added':len(all_added),'regions':stats,'total':len(merged)},ensure_ascii=False))

if __name__=='__main__':main()
