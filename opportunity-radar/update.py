#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zero-cost public-data updater for B2B Opportunity Radar.
Standard library only. Fails loudly if the official source becomes stale/broken.
"""
from __future__ import annotations
import datetime as dt, hashlib, html, json, re, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
EVENTS=ROOT/'events.json'; STATUS=ROOT/'status.json'
LIST_URL='https://investtaiwan.nat.gov.tw/threeMajorNewsPageList'
BASE='https://investtaiwan.nat.gov.tw/'
UA='Mozilla/5.0 OpportunityRadar/0.4 (+https://cbradarlab.github.io/opportunity-radar/)'
MAX_ARTICLES=8; STALE_DAYS=21; HTTP_TIMEOUT=12

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
BLACK={'投資臺灣','三大方案','經濟部','中小企業','臺商回臺','根留臺灣','智慧製造','人工智慧','半導體','供應鏈','新能源','太陽能'}

def fetch(url:str)->str:
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept-Language':'zh-TW,zh;q=0.9'})
    with urllib.request.urlopen(req,timeout=HTTP_TIMEOUT) as r:
        raw=r.read(); enc=r.headers.get_content_charset() or 'utf-8'
    try:return raw.decode(enc,'replace')
    except LookupError:return raw.decode('utf-8','replace')

def textify(s:str)->str:
    s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s)
    s=re.sub(r'(?s)<[^>]+>',' ',s)
    return re.sub(r'\s+',' ',html.unescape(s)).strip()

def article_links(list_html:str):
    found=[]
    for m in re.finditer(r'''href=["']([^"']*threeMajorNewsPage[^"']*newsNum=\d+[^"']*)["']''',list_html,re.I):
        u=urllib.parse.urljoin(BASE,html.unescape(m.group(1)))
        if u not in found: found.append(u)
    return found[:MAX_ARTICLES]

def extract_date(article_text:str,fallback=''):
    ds=re.findall(r'20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}',article_text)
    if not ds:return fallback
    p=ds[0].replace('/','-').replace('.','-').split('-')
    return f'{int(p[0]):04d}-{int(p[1]):02d}-{int(p[2]):02d}'

def explicit_needs(t:str):
    low=t.lower(); out={}
    for cat,phrases in RULES.items():
        hits=[p for p in phrases if p.lower() in low]
        if hits:out[cat]=list(dict.fromkeys(hits))
    return out

def companies(t:str):
    cand=[]
    for x in re.findall(r'「([^」]{2,30})」',t):
        x=re.sub(r'\s+','',x).strip('，。；：:「」()（）')
        if x and x not in BLACK and not any(w in x for w in ['方案','市場','產業','基地','新廠','智慧','投資']):cand.append(x)
    pat=r'([\u4e00-\u9fffA-Za-z0-9·]{2,22}(?:股份有限公司|有限公司|科技|工業|企業|光電|電子|鋁業|化學|精密|食品|實業|材料|國際))'
    cand+=re.findall(pat,t); clean=[]
    for x in cand:
        x=x.strip()
        if 2<=len(x)<=30 and x not in BLACK and x not in clean:clean.append(x)
    return clean[:5]

def amount_billion(t:str):
    ms=re.findall(r'(?:投資|斥資|加碼)[^。；，]{0,30}?([0-9]+(?:\.[0-9]+)?)\s*億',t)
    return float(ms[0]) if ms else 0

def guess_city(t:str):
    for c in ['基隆','台北','臺北','新北','桃園','新竹','苗栗','台中','臺中','彰化','南投','雲林','嘉義','台南','臺南','高雄','屏東','宜蘭','花蓮','台東','臺東','澎湖']:
        if c in t:return c.replace('臺','台')
    return ''

def event_id(company,date,source):return hashlib.sha1(f'{company}|{date}|{source}'.encode()).hexdigest()[:16]
def load_events():
    try:return json.loads(EVENTS.read_text(encoding='utf-8'))
    except Exception:return []

def main():
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    list_html=fetch(LIST_URL); list_text=textify(list_html)
    dates=re.findall(r'20\d{2}-\d{2}-\d{2}',list_text); latest=max(dates) if dates else ''
    links=article_links(list_html)
    if not links:raise RuntimeError('No official article links discovered')
    autos=[]; failures=0; checked=0
    for url in links:
        try:
            txt=textify(fetch(url)); checked+=1; needs=explicit_needs(txt)
            if not needs:continue
            date=extract_date(txt,latest); comps=companies(txt)
            if not comps:continue
            amt=amount_billion(txt); city=guess_city(txt)
            for comp in comps:
                score=min(99,82+min(12,len(needs)*2)+(3 if amt>=5 else 0)+(2 if amt>=20 else 0))
                autos.append({'company':comp,'date':date,'city':city,'district':'','amount':amt,'stage':'官方投資/擴產公告','industry':'','explicit':list(needs.keys()),'explicit_evidence':needs,'inferred':[],'contact':'公司名稱已識別｜公開聯絡資料可再補','source':url,'source_type':'投資臺灣三大方案｜自動抓取','score':score,'id':event_id(comp,date,url),'auto':True})
        except Exception as e:
            failures+=1; print('WARN',url,repr(e),file=sys.stderr)
    if checked==0:raise RuntimeError('All official articles failed')
    if not autos:raise RuntimeError('Official pages fetched but no purchase-intent events parsed')
    if not latest:raise RuntimeError('Latest official date missing')
    age=(now.date()-dt.date.fromisoformat(latest)).days
    if age>STALE_DAYS:raise RuntimeError(f'Official source stale: latest={latest}, age={age}d')
    manual=[e for e in load_events() if not e.get('auto')]
    byid={e['id']:e for e in autos if e.get('id')}
    merged=manual+sorted(byid.values(),key=lambda e:(e.get('date',''),e.get('score',0)),reverse=True)
    EVENTS.write_text(json.dumps(merged,ensure_ascii=False,indent=2),encoding='utf-8')
    status={'updated_at':now.isoformat(timespec='seconds'),'source_status':'PASS_LIVE_REFRESH_HEALTHY','latest_source_date':latest,'articles_checked':checked,'article_failures':failures,'auto_event_count':len(byid),'total_event_count':len(merged),'warnings':[],'data_cost_ntd':0,'ai_api_required':False}
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(status,ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except Exception as e:print('FATAL:',repr(e),file=sys.stderr);sys.exit(2)
