#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zero-cost public-data updater for B2B Opportunity Radar.
Standard library only. Multi-source: Invest Taiwan purchase-intent news +
national building-permit early signals. Keeps explicit vs inferred demand separate.
"""
from __future__ import annotations
import datetime as dt, hashlib, html, json, re, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
EVENTS=ROOT/'events.json'; STATUS=ROOT/'status.json'; TOPIC_DIR=ROOT/'topics'
LIST_URL='https://investtaiwan.nat.gov.tw/threeMajorNewsPageList'
BASE='https://investtaiwan.nat.gov.tw/'
BUILDLIC_URL='https://building-apply.publicwork.ntpc.gov.tw/opendata/OpenDataSearchUrl.do'
BUILDLIC_DOC='https://building-apply.publicwork.ntpc.gov.tw/opendata/docs/a1.html'
SITE='https://cbradarlab.github.io/opportunity-radar/'
UA='Mozilla/5.0 OpportunityRadar/0.8 (+https://cbradarlab.github.io/opportunity-radar/)'
MAX_ARTICLES=8; STALE_DAYS=21; HTTP_TIMEOUT=12
BUILD_MONTHS=2; BUILD_MAX_PAGES=3; BUILD_TERMS=('工廠','廠房','倉庫')

RULES={
'空壓機':['空壓機','空壓系統','壓縮空氣'],
'冰水主機/空調':['冰水主機','節能空調','空調系統','恆溫恆濕'],
'純水/水處理':['純水系統','水循環','回收水','廢水處理','製程廢液','水處理'],
'智慧倉儲':['智慧倉儲','自動倉儲','智能倉儲','自動化倉儲'],
'冷鏈':['冷凍倉儲','冷藏倉儲','低溫物流','冷鏈'],
'機器手臂':['機械手臂','機器手臂','機械臂'],
'機器視覺/AOI':['機器視覺','視覺檢測','影像辨識','AI影像辨識','AI智慧檢測','自動光學檢驗','AOI','視覺線上配光'],
'MES/製程追溯':['MES','製程追溯','生產履歷','生產管理系統','智慧資訊平台'],
'設備聯網/IIoT':['設備聯網','物聯網','IIoT','機台聯網'],
'自動控制/PLC':['自動控制','自動化控制','數位控制','PLC'],
'感測器':['感測器','感測設備'],
'能源管理':['能源管理','能源監管','能源管理系統','智慧電表'],
'太陽能':['太陽能','太陽光電'],
'儲能':['儲能','大型儲能','儲能系統'],
'自動化設備':['自動化設備','智能設備','智慧設備','自動化生產','智慧產線','智能產線'],
'雷射設備':['雷射銲接','雷射焊接','雷射設備'],
'無塵室':['無塵室','潔淨室'],
'RFID':['RFID','射頻識別']
}
TOPICS={
'air-compressor':('空壓機','空壓機採購商機','追蹤台灣新廠與擴產公告中直接提到空壓機、壓縮空氣設備的企業投資案。'),
'smart-warehouse':('智慧倉儲','智慧倉儲採購商機','整理官方投資公告中明示智慧倉儲、自動倉儲與相關新廠擴產需求。'),
'machine-vision':('機器視覺/AOI','機器視覺與 AOI 採購商機','追蹤新廠、擴產與智慧製造案中的機器視覺、AOI、影像辨識需求。'),
'mes':('MES/製程追溯','MES 與製程追溯採購商機','整理企業投資案中明示的 MES、生產管理、製程追溯與智慧資訊平台需求。'),
'solar':('太陽能','企業太陽能採購商機','追蹤新廠與擴產投資案中官方明示的太陽能、太陽光電設備需求。')
}
BLACK_PREFIX=('投資臺灣事務所','截至目前','後續尚有','本次投資','新廠','新產線','該公司','此次投資','資料來源','新聞發言人')
COMPANY_START=re.compile(r'^([^，。；：\s]{2,24}?)(?=為|深耕|成立於|成立|創立|主要|專注|隸屬|是|以)')
CORP_TOKENS=('股份有限公司','有限公司','公司','科技','工業','企業','實業','電子','材料','化學','製造','食品','物流','生技','能源','精密','機械','光電','電機')
DEV_TOKENS=('建設有限公司','建設股份有限公司','營造有限公司','營造股份有限公司','開發建設')
CITY_NAMES=('基隆市','台北市','臺北市','新北市','桃園市','新竹市','新竹縣','苗栗縣','台中市','臺中市','彰化縣','南投縣','雲林縣','嘉義市','嘉義縣','台南市','臺南市','高雄市','屏東縣','宜蘭縣','花蓮縣','台東縣','臺東縣','澎湖縣','金門縣','連江縣')

def fetch(url:str)->str:
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept-Language':'zh-TW,zh;q=0.9'})
    with urllib.request.urlopen(req,timeout=HTTP_TIMEOUT) as r:
        raw=r.read(); enc=r.headers.get_content_charset() or 'utf-8'
    try:return raw.decode(enc,'replace')
    except LookupError:return raw.decode('utf-8','replace')

def plain_text(s:str)->str:
    s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s)
    s=re.sub(r'(?s)<[^>]+>',' ',s)
    return re.sub(r'\s+',' ',html.unescape(s)).strip()

def block_lines(s:str):
    s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s)
    s=re.sub(r'(?i)</(?:p|div|li|h[1-6]|section|article|tr)>|<br\s*/?>','\n',s)
    s=re.sub(r'(?s)<[^>]+>',' ',s); s=html.unescape(s)
    out=[]
    for line in s.splitlines():
        line=re.sub(r'\s+',' ',line).strip()
        if line:out.append(line)
    return out

def article_links(list_html:str):
    found=[]
    for m in re.finditer(r'''href=["']([^"']*threeMajorNewsPage[^"']*newsNum=\d+[^"']*)["']''',list_html,re.I):
        u=urllib.parse.urljoin(BASE,html.unescape(m.group(1)))
        if u not in found:found.append(u)
    return found[:MAX_ARTICLES]

def extract_date(text:str,fallback=''):
    ds=re.findall(r'20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}',text)
    if not ds:return fallback
    p=ds[0].replace('/','-').replace('.','-').split('-')
    return f'{int(p[0]):04d}-{int(p[1]):02d}-{int(p[2]):02d}'

def explicit_needs(t:str):
    low=t.lower(); out={}
    for cat,phrases in RULES.items():
        hits=[p for p in phrases if p.lower() in low]
        if hits:out[cat]=list(dict.fromkeys(hits))
    return out

def detail_paragraphs(raw:str):
    lines=block_lines(raw); start=0
    for i,x in enumerate(lines):
        if '投資臺灣事務所今' in x and ('通過' in x or '投資' in x):start=i+1; break
    out=[]
    for x in lines[start:]:
        if '投資臺灣事務所新聞發言人' in x or x.startswith('資料來源'):break
        if len(x)<60:continue
        m=COMPANY_START.search(x)
        if not m:continue
        comp=m.group(1).strip('「」')
        if comp.startswith(BLACK_PREFIX) or comp.startswith('某'):continue
        if not any(k in x for k in ['投資','新廠','擴增','擴大','產線','設備','建置','興建','導入','採購']):continue
        out.append((comp,x))
    return out

def amount_billion(t:str):
    pats=[r'(?:總?投資(?:金額)?|投資金額|本案投資金額|總金額|斥資|加碼)[^。；，]{0,28}?([0-9]+(?:\.[0-9]+)?)\s*億',r'([0-9]+(?:\.[0-9]+)?)\s*億(?:元)?(?:投資|建廠|擴廠|擴產)']
    for pat in pats:
        ms=re.findall(pat,t)
        if ms:return float(ms[0])
    return 0

def guess_city(t:str):
    found=[]
    for c in CITY_NAMES:
        if c in t:
            n=c.replace('臺','台').replace('市','').replace('縣','')
            if n not in found:found.append(n)
    return '/'.join(found[:2])

def event_id(company,date,source):return hashlib.sha1(f'{company}|{date}|{source}'.encode()).hexdigest()[:16]
def load_events():
    try:return json.loads(EVENTS.read_text(encoding='utf-8'))
    except Exception:return []
def h(s):return html.escape(str(s or ''),quote=True)

def roc_month(d:dt.date)->str:return f'{d.year-1911:03d}年{d.month:02d}月'
def recent_months(now:dt.datetime,n:int):
    y,m=now.year,now.month; out=[]
    for _ in range(n):
        out.append(dt.date(y,m,1)); m-=1
        if m==0:y-=1;m=12
    return out

def roc_date(v)->str:
    s=re.sub(r'\D','',str(v or ''))
    if len(s)>=7:
        try:
            y=int(s[:3])+1911; m=int(s[3:5]); d=int(s[5:7]); return f'{y:04d}-{m:02d}-{d:02d}'
        except Exception:return ''
    m=re.search(r'(\d{2,3})年(\d{1,2})月(\d{1,2})日?',str(v or ''))
    if m:
        try:return f'{int(m.group(1))+1911:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
        except Exception:return ''
    return ''

def flatten_strings(x):
    out=[]
    if isinstance(x,dict):
        for v in x.values():out.extend(flatten_strings(v))
    elif isinstance(x,list):
        for v in x:out.extend(flatten_strings(v))
    elif x is not None:out.append(str(x))
    return out

def buildlic_rows(month:dt.date,term:str):
    allrows=[]
    for p in range(BUILD_MAX_PAGES):
        params={'d':'OPENDATA','c':'BUILDLIC','Start':str(p*100+1),'執照類別':'建造執照','發照日期':roc_month(month),'樓層概要.樓層用途':f'.*{term}.*'}
        url=BUILDLIC_URL+'?'+urllib.parse.urlencode(params)
        raw=fetch(url); obj=json.loads(raw)
        rows=obj.get('data',[]) if isinstance(obj,dict) else (obj if isinstance(obj,list) else [])
        if not isinstance(rows,list):rows=[]
        allrows.extend(x for x in rows if isinstance(x,dict))
        if len(rows)<100:break
    return allrows

def clean_company(v:str)->str:
    s=re.sub(r'\s+','',str(v or '')).strip('：:，,；;')
    s=re.sub(r'(?:負責人|代表人)[：:].*$','',s)
    s=re.sub(r'^\([A-Z]\d+\)|^[A-Z]\d+[.、]?','',s)
    return s.strip('「」()（）')

def permit_city(row):
    txt=' '.join(flatten_strings(row))
    for c in CITY_NAMES:
        if c in txt:return c.replace('臺','台').replace('市','').replace('縣','')
    return ''

def permit_district(row):
    for key in ('門牌','地號'):
        xs=row.get(key) or []
        if isinstance(xs,dict):xs=[xs]
        if isinstance(xs,list):
            for x in xs:
                if isinstance(x,dict) and x.get('行政區'):return str(x.get('行政區'))
    return ''

def permit_uses(row):
    xs=row.get('樓層概要') or []
    if isinstance(xs,dict):xs=[xs]
    vals=[]
    if isinstance(xs,list):
        for x in xs:
            if isinstance(x,dict):
                v=str(x.get('樓層用途') or '')
                if v and any(t in v for t in BUILD_TERMS):vals.append(v)
    return list(dict.fromkeys(vals))

def permit_area(row):
    for k in ('總樓地板面積','建築面積','基地面積'):
        v=str(row.get(k) or '').replace(',','')
        m=re.search(r'[0-9]+(?:\.[0-9]+)?',v)
        if m:
            try:return float(m.group(0))
            except Exception:pass
    return 0.0

def permit_inferred(uses):
    text=' '.join(uses); out=['消防/弱電']
    if '工廠' in text or '廠房' in text:out+=['冰水主機/空調','空壓機']
    if '倉庫' in text:out+=['智慧倉儲']
    return list(dict.fromkeys(out))

def buildlic_events(now):
    events=[]; seen=set(); queries=0; failures=0; rawrows=0
    for month in recent_months(now,BUILD_MONTHS):
        for term in BUILD_TERMS:
            try:rows=buildlic_rows(month,term); queries+=1
            except Exception as e:
                failures+=1; print('WARN BUILDLIC',roc_month(month),term,repr(e),file=sys.stderr); continue
            rawrows+=len(rows)
            for row in rows:
                comp=clean_company(row.get('起造人代表人',''))
                if len(comp)<3 or not any(t in comp for t in CORP_TOKENS) or any(t in comp for t in DEV_TOKENS):continue
                uses=permit_uses(row)
                if not uses:continue
                lic=str(row.get('核發執照字號') or row.get('_id') or '')
                date=roc_date(row.get('發照日期')) or month.isoformat()
                key=(comp,lic,date)
                if key in seen:continue
                seen.add(key)
                start=roc_date(row.get('實際開工日期')); area=permit_area(row); inf=permit_inferred(uses)
                stage=('已開工' if start else '建造執照已核發')+'｜'+'／'.join(uses[:3])
                score=68+(5 if start else 0)+(3 if area>=5000 else 0)+(3 if area>=15000 else 0)
                contact='起造公司已識別'
                contractor=str(row.get('承造人') or '').strip()
                if contractor:contact+=f'｜承造人：{contractor}'
                source=BUILDLIC_DOC
                events.append({'company':comp,'date':start or date,'city':permit_city(row),'district':permit_district(row),'amount':0,'stage':stage,'industry':'工業建築早期訊號','explicit':[],'explicit_evidence':{},'inferred':inf,'contact':contact,'source':source,'source_type':'全國建管 OpenData｜建造執照','score':min(88,score),'id':event_id(comp,date,'BUILDLIC:'+lic),'auto':True,'permit_no':lic,'floor_area_m2':area,'permit_date':date,'start_date':start,'building_uses':uses})
    return events,{'buildlic_queries':queries,'buildlic_failures':failures,'buildlic_raw_rows':rawrows,'buildlic_event_count':len(events)}

def render_topics(events, updated):
    TOPIC_DIR.mkdir(exist_ok=True)
    for slug,(key,title,desc) in TOPICS.items():
        matches=[e for e in events if key in (e.get('explicit') or [])]
        matches.sort(key=lambda e:(e.get('date',''),e.get('score',0)),reverse=True)
        cards=[]
        for e in matches:
            evidence='、'.join((e.get('explicit_evidence') or {}).get(key,[])) or key
            amount=f"｜投資約 {h(e.get('amount'))} 億元" if e.get('amount') else ''
            cards.append(f'''<article><h2>{h(e.get('company'))}</h2><p class="meta">{h(e.get('date'))}｜{h(e.get('city') or '地區待補')}｜商機分數 {h(e.get('score'))}</p><p><b>官方明示：</b>{h(evidence)}</p><p>{h(e.get('stage'))}{amount}</p><a href="{h(e.get('source'))}" rel="nofollow noopener" target="_blank">查看官方來源 ↗</a></article>''')
        if not cards:cards=['<div class="empty">目前近期資料中尚無符合的官方明示案件；系統仍會每天自動更新。</div>']
        canonical=f'{SITE}topics/{slug}.html'
        body=f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{h(title)}｜企業採購商機雷達</title><meta name="description" content="{h(desc)}"><link rel="canonical" href="{canonical}"><style>body{{margin:0;background:#f6f8fc;color:#172033;font-family:system-ui,-apple-system,"Segoe UI","Noto Sans TC",sans-serif}}main{{max-width:920px;margin:auto;padding:36px 18px 70px}}header{{background:#0f172a;color:white;border-radius:22px;padding:30px}}h1{{font-size:36px;margin:8px 0}}header p{{line-height:1.7;color:#dbeafe}}nav{{margin:18px 0}}nav a{{margin-right:12px;color:#1d4ed8}}article,.empty{{background:white;border:1px solid #e2e8f0;border-radius:16px;padding:20px;margin:14px 0}}article h2{{margin:0 0 7px}}.meta{{color:#64748b;font-size:14px}}article a{{color:#1d4ed8;font-weight:700;text-decoration:none}}footer{{color:#64748b;font-size:13px;margin-top:28px;line-height:1.7}}</style></head><body><main><header><small>企業採購商機雷達</small><h1>{h(title)}</h1><p>{h(desc)} A 級只收官方原文明示的需求，不把一般產業猜測混進來。</p></header><nav><a href="../">搜尋全部商機</a><a href="./smart-warehouse.html">智慧倉儲</a><a href="./machine-vision.html">機器視覺</a><a href="./mes.html">MES</a><a href="./solar.html">太陽能</a><a href="./air-compressor.html">空壓機</a></nav><p>目前符合：<b>{len(matches)}</b> 筆｜資料更新：{h(updated)}</p>{''.join(cards)}<footer>資料來自政府與官方公開資訊，自動更新。商機資訊不代表採購、得標或成交保證。</footer></main></body></html>'''
        (TOPIC_DIR/f'{slug}.html').write_text(body,encoding='utf-8')

def main():
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    list_html=fetch(LIST_URL); list_text=plain_text(list_html)
    dates=re.findall(r'20\d{2}-\d{2}-\d{2}',list_text); latest=max(dates) if dates else ''
    links=article_links(list_html)
    if not links:raise RuntimeError('No official article links discovered')
    invest=[]; failures=0; checked=0; paragraphs=0
    for url in links:
        try:
            raw=fetch(url); checked+=1; article_text=plain_text(raw); date=extract_date(article_text,latest)
            for comp,seg in detail_paragraphs(raw):
                paragraphs+=1; needs=explicit_needs(seg)
                if not needs:continue
                amt=amount_billion(seg); city=guess_city(seg)
                score=min(99,82+min(12,len(needs)*2)+(3 if amt>=5 else 0)+(2 if amt>=20 else 0))
                invest.append({'company':comp,'date':date,'city':city,'district':'','amount':amt,'stage':'官方投資/擴產公告','industry':'','explicit':list(needs.keys()),'explicit_evidence':needs,'inferred':[],'contact':'公司名稱已識別｜公開聯絡資料可再補','source':url,'source_type':'投資臺灣三大方案｜自動抓取','score':score,'id':event_id(comp,date,url),'auto':True})
        except Exception as e:
            failures+=1; print('WARN',url,repr(e),file=sys.stderr)
    if checked==0:raise RuntimeError('All official articles failed')
    if paragraphs==0:raise RuntimeError('Official pages fetched but company paragraphs were not detected')
    if not invest:raise RuntimeError('Company paragraphs detected but no purchase-intent events parsed')
    if not latest:raise RuntimeError('Latest official date missing')
    age=(now.date()-dt.date.fromisoformat(latest)).days
    if age>STALE_DAYS:raise RuntimeError(f'Official source stale: latest={latest}, age={age}d')

    permits,pstats=buildlic_events(now)
    manual=[e for e in load_events() if not e.get('auto')]
    manual_ids={e.get('id') for e in manual if e.get('id')}
    all_auto=invest+permits
    byid={e['id']:e for e in all_auto if e.get('id') and e.get('id') not in manual_ids}
    if len({e['id'] for e in invest if e.get('id')})>paragraphs:raise RuntimeError('Parser regression: more investment events than company paragraphs')
    merged=manual+sorted(byid.values(),key=lambda e:(e.get('date',''),e.get('score',0)),reverse=True)
    ids=[e.get('id') for e in merged if e.get('id')]
    if len(ids)!=len(set(ids)):raise RuntimeError('Duplicate event IDs after merge')
    EVENTS.write_text(json.dumps(merged,ensure_ascii=False,indent=2),encoding='utf-8')
    render_topics(merged,now.isoformat(timespec='minutes'))
    unique_companies=len({re.sub(r'\s+','',e.get('company','')) for e in merged if e.get('company')})
    warnings=[]
    if pstats['buildlic_queries']==0 or pstats['buildlic_event_count']==0:warnings.append('BUILDLIC_NO_EVENTS')
    if pstats['buildlic_failures']>0:warnings.append(f"BUILDLIC_FAILURES={pstats['buildlic_failures']}")
    status={'updated_at':now.isoformat(timespec='seconds'),'source_status':'PASS_MULTI_SOURCE_LIVE_REFRESH','latest_source_date':latest,'articles_checked':checked,'article_failures':failures,'company_paragraphs_checked':paragraphs,'investment_auto_event_count':len({e['id'] for e in invest if e.get('id')}),'buildlic_event_count':pstats['buildlic_event_count'],'auto_event_count':len(byid),'seed_event_count':len(manual),'total_event_count':len(merged),'unique_company_count':unique_companies,'seo_topic_pages':len(TOPICS),'warnings':warnings,'data_cost_ntd':0,'ai_api_required':False,**pstats}
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(status,ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except Exception as e:print('FATAL:',repr(e),file=sys.stderr);sys.exit(2)