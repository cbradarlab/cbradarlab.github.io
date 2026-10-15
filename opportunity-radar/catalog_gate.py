#!/usr/bin/env python3
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CAT=json.loads((ROOT/'product_catalog.json').read_text(encoding='utf-8'))
EV=json.loads((ROOT/'events.json').read_text(encoding='utf-8'))
TESTS=[
'消防工程','監視器','門禁','配電盤','UPS','發電機','工業地坪','環氧樹脂地坪','鋼構工程','電梯',
'空壓機','變頻空壓機','工業空調','冰水主機','冷卻水塔','真空泵浦','集塵設備','配管工程','特氣系統','乾燥機',
'無塵室','純水系統','廢水處理','廢氣處理','洗滌塔','化學品供應系統',
'機械手臂','協作機器人','PLC','SCADA','感測器','變頻器','機器視覺','AOI','設備聯網','工業電腦',
'智慧倉儲','ASRS','AGV','AMR','堆高機','輸送帶','自動分揀','冷凍庫','貨架',
'ERP','MES','WMS','QMS','CMMS','APS','資安','伺服器',
'太陽能','儲能','能源管理','碳盤查','熱泵',
'CNC','雷射切割機','射出機','包裝機','貼標機',
'三次元量測','環境試驗箱','實驗室設備','ISO認證',
'馬達','軸承','氣動元件','工業閥門','CNC刀具','治具',
'保全','清潔服務','飲水機','辦公家具','制服','安全鞋',
'人力派遣','人才招募','職安訓練','產物保險','報關'
]
def norm(s): return re.sub(r'\s+','',str(s)).lower()
def resolve(q):
 qn=norm(q); cand=[]
 for f in CAT['families']:
  for a in f['aliases']:
   an=norm(a)
   if qn==an or qn in an or an in qn: cand.append((len(an),f))
 return max(cand,key=lambda x:x[0])[1] if cand else None
def blob(e):
 ev=[]
 for v in (e.get('explicit_evidence') or {}).values(): ev += v or []
 return norm(' '.join(map(str,[e.get('company',''),e.get('stage',''),e.get('industry',''),e.get('title',''),*(e.get('explicit') or []),*(e.get('inferred') or []),*ev])))
def matches(f,e):
 b=blob(e)
 if any(norm(t) in b for t in f.get('strong_terms',[])): return True
 sb=norm(' '.join([e.get('stage',''),e.get('industry',''),e.get('title','')]))
 return any(norm(t) in sb for t in f.get('stage_terms',[]))
resolved=[]; event_ok=[]; bad=[]
for q in TESTS:
 f=resolve(q)
 if not f:
  bad.append((q,'UNRESOLVED'));continue
 resolved.append(q)
 n=sum(1 for e in EV if matches(f,e))
 if n: event_ok.append(q)
 else: bad.append((q,f['id']+':NO_EVENT'))
coverage=len(resolved)/len(TESTS)
event_rate=len(event_ok)/len(TESTS)
print(json.dumps({'tests':len(TESTS),'resolved':len(resolved),'coverage':round(coverage,4),'event_match':len(event_ok),'event_match_rate':round(event_rate,4),'bad':bad},ensure_ascii=False))
if coverage < .95 or event_rate < .80:
 raise SystemExit(1)
