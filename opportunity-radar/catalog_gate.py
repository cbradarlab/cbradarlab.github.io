#!/usr/bin/env python3
import json,re
from pathlib import Path
R=Path(__file__).resolve().parent
CAT=json.loads((R/'product_catalog.json').read_text(encoding='utf-8'))
RULES=json.loads((R/'intent_rules.json').read_text(encoding='utf-8'))
EV=json.loads((R/'events.json').read_text(encoding='utf-8'))
TESTS=[
('消防工程','factory_mep'),('工業地坪','factory_mep'),('配電盤','factory_mep'),('UPS','factory_mep'),
('堆高機','warehouse_logistics'),('冷凍庫','warehouse_logistics'),('門禁','factory_mep'),('監視器','factory_mep'),
('弱電','factory_mep'),('ERP','enterprise_software'),('MES','enterprise_software'),('WMS','enterprise_software'),
('AOI','automation'),('機器手臂','automation'),('空壓機','hvac_utilities'),('冰水主機','hvac_utilities'),
('廢水處理','cleanroom_environment'),('純水','cleanroom_environment'),('CNC刀具','maintenance_parts'),('治具','maintenance_parts'),
('量測儀器','quality_lab'),('包裝機','production_machinery'),('保全','facility_operations'),('清潔','facility_operations'),
('人力派遣','business_services'),('制服','facility_operations'),('消防設備','factory_mep'),('高低壓配電','factory_mep'),
('發電機','factory_mep'),('冷卻水塔','hvac_utilities'),('集塵設備','hvac_utilities'),('特氣系統','hvac_utilities'),
('無塵室','cleanroom_environment'),('機械手臂','automation'),('PLC','automation'),('SCADA','automation'),
('機器視覺','automation'),('AGV','warehouse_logistics'),('AMR','warehouse_logistics'),('自動倉儲','warehouse_logistics'),
('QMS','enterprise_software'),('CMMS','enterprise_software'),('APS','enterprise_software'),('資安','enterprise_software'),
('太陽能','energy_esg'),('儲能','energy_esg'),('能源管理','energy_esg'),('CNC','production_machinery'),
('雷射切割機','production_machinery'),('射出機','production_machinery'),('三次元量測','quality_lab'),('馬達','maintenance_parts'),
('軸承','maintenance_parts'),('氣動元件','maintenance_parts'),('工業閥門','maintenance_parts'),('安全鞋','facility_operations'),
('職安訓練','business_services'),('報關','business_services'),('包裝設備','production_machinery'),('冷藏庫','warehouse_logistics')
]
def n(s): return re.sub(r'\s+','',str(s or '')).lower()
def vals(e):
 out=[]
 for v in (e.get('explicit_evidence') or {}).values(): out += [str(x) for x in (v or [])]
 return out
def blob(e): return n(' '.join(map(str,[e.get('company',''),e.get('city',''),e.get('district',''),e.get('stage',''),e.get('industry',''),e.get('title',''),*(e.get('explicit') or []),*(e.get('inferred') or []),*vals(e)])))
def stage(e): return n(' '.join(map(str,[e.get('stage',''),e.get('title','')])))
def has(text,terms): return any(n(t) in text for t in (terms or []) if n(t))
def family(q):
 qn=n(q); best=None
 for f in CAT.get('families',[]):
  for a in f.get('aliases',[]):
   an=n(a)
   if qn==an or qn in an or an in qn:
    s=(1 if qn==an else 0,len(an))
    if best is None or s>best[0]: best=(s,f)
 return best[1] if best else None
def intent(q):
 qn=n(q); best=None
 for i in RULES.get('intents',[]):
  for a in [i.get('canonical',''),*(i.get('aliases') or [])]:
   an=n(a)
   if qn==an or qn in an or an in qn:
    s=(1 if qn==an else 0,len(an))
    if best is None or s>best[0]: best=(s,i)
 return best[1] if best else None
def ruleok(r,e):
 b=blob(e); s=stage(e)
 if r.get('stage_any') and not has(s,r['stage_any']): return False
 if r.get('blob_any') and not has(b,r['blob_any']): return False
 if r.get('exclude_any') and has(b,r['exclude_any']): return False
 return True
def profile_for(q):
 i=intent(q)
 if i: return i.get('profile'),i
 f=family(q)
 return (RULES.get('fallback_profiles',{}).get(f.get('id')) if f else None),None
def classify(q,e):
 i=intent(q)
 if i:
  x=n(' '.join(map(str,[*(e.get('explicit') or []),*vals(e)])))
  if any(n(t) and n(t) in x for t in [i.get('canonical',''),*(i.get('aliases') or [])]): return 'A'
  y=n(' '.join(map(str,e.get('inferred') or [])))
  if any(n(t) and n(t) in y for t in [i.get('canonical',''),*(i.get('aliases') or [])]): return 'B'
 p,_=profile_for(q)
 for r in RULES.get('profiles',{}).get(p,{}).get('rules',[]):
  if ruleok(r,e): return r.get('level','C')
 return None
bad=[]; event_bad=[]; resolved=0; correct=0; event_ok=0
for q,expected in TESTS:
 f=family(q)
 if f: resolved+=1
 if f and f.get('id')==expected:
  correct+=1
  if any(classify(q,e) for e in EV): event_ok+=1
  else: event_bad.append((q,expected,'NO_EVENT'))
 else: bad.append((q,expected,f.get('id') if f else None))
coverage=correct/len(TESTS); event_rate=event_ok/len(TESTS)
GEN={'company':'測試','stage':'新廠動土','industry':'一般製造','title':'一般製造業新廠動土','explicit':[],'inferred':[],'explicit_evidence':{}}
generic=[q for q,_ in TESTS if classify(q,GEN)]
generic_b=[q for q,_ in TESTS if classify(q,GEN) in ('A','B')]
g_rate=len(generic)/len(TESTS); gb_rate=len(generic_b)/len(TESTS)
COUNTER=[
({'stage':'智慧製造產線升級','industry':'電子零組件','title':'導入AI影像檢測與智慧製造','explicit':[],'inferred':[],'explicit_evidence':{}},['AOI','機器視覺','MES','機器手臂'],['冷凍庫','包裝機']),
({'stage':'冷凍食品新廠','industry':'冷凍調理食品','title':'新建冷鏈與食品產線','explicit':[],'inferred':[],'explicit_evidence':{}},['冷凍庫','包裝機'],['CNC','CNC刀具']),
({'stage':'擴充產能','industry':'精密金屬加工','title':'新增CNC加工產線','explicit':[],'inferred':[],'explicit_evidence':{}},['CNC','CNC刀具','治具'],['冷凍庫','純水'])
]
cb=[]
for k,(e,yes,no) in enumerate(COUNTER,1):
 for q in yes:
  if not classify(q,e): cb.append((k,q,'EXPECTED_MATCH_MISSING'))
 for q in no:
  if classify(q,e): cb.append((k,q,'UNWANTED_MATCH'))
out={'tests':len(TESTS),'resolved':resolved,'correct':correct,'coverage':round(coverage,4),'event_match':event_ok,'event_match_rate':round(event_rate,4),'generic_match_count':len(generic),'generic_match_rate':round(g_rate,4),'generic_B_count':len(generic_b),'generic_B_rate':round(gb_rate,4),'bad_resolve':bad,'event_bad':event_bad,'counterexample_bad':cb,'rules_version':RULES.get('version')}
print(json.dumps(out,ensure_ascii=False,indent=2))
if coverage<.95: raise SystemExit('FAIL_RESOLUTION')
if event_rate<.80: raise SystemExit('FAIL_EVENT_MATCH')
if g_rate>.45 or gb_rate>.35: raise SystemExit('FAIL_GENERIC_POLLUTION')
if cb: raise SystemExit('FAIL_COUNTEREXAMPLES')
print('PASS_PRODUCT_SERVICE_COVERAGE_V2')
