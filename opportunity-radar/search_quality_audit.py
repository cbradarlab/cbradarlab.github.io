#!/usr/bin/env python3
import json,re,itertools,statistics
from pathlib import Path
R=Path(__file__).resolve().parent
CAT=json.loads((R/'product_catalog.json').read_text(encoding='utf-8'))
RULES=json.loads((R/'intent_rules.json').read_text(encoding='utf-8'))
EV=json.loads((R/'events.json').read_text(encoding='utf-8'))
QUERIES=['消防工程','工業地坪','配電盤','UPS','堆高機','冷凍庫','門禁','監視器','弱電','ERP','MES','WMS','AOI','機器手臂','空壓機','冰水主機','廢水處理','純水','CNC刀具','治具','量測儀器','包裝機','保全','清潔','人力派遣','制服','消防設備','高低壓配電','發電機','冷卻水塔','集塵設備','特氣系統','無塵室','機械手臂','PLC','SCADA','機器視覺','AGV','AMR','自動倉儲','QMS','CMMS','APS','資安','太陽能','儲能','能源管理','CNC','雷射切割機','射出機','三次元量測','馬達','軸承','氣動元件','工業閥門','安全鞋','職安訓練','報關','包裝設備','冷藏庫']
def n(s): return re.sub(r'\s+','',str(s or '')).lower()
def evidence(e):
 out=[]
 for v in (e.get('explicit_evidence') or {}).values(): out += [str(x) for x in (v or [])]
 return out
def blob(e): return n(' '.join(map(str,[e.get('company',''),e.get('city',''),e.get('district',''),e.get('stage',''),e.get('industry',''),e.get('title',''),*(e.get('explicit') or []),*(e.get('inferred') or []),*evidence(e)])))
def stage(e): return n(' '.join(map(str,[e.get('stage',''),e.get('title','')])))
def has(text,terms): return any(n(t) in text for t in (terms or []) if n(t))
def best(q,items,aliases):
 qn=n(q); hit=None
 for item in items:
  for a in aliases(item):
   an=n(a)
   if an and (qn==an or qn in an or an in qn):
    score=(1 if qn==an else 0,len(an))
    if hit is None or score>hit[0]: hit=(score,item,a)
 return hit
def family(q):
 x=best(q,CAT.get('families',[]),lambda f:f.get('aliases',[])); return x[1] if x else None
def intent(q):
 x=best(q,RULES.get('intents',[]),lambda i:[i.get('canonical',''),*(i.get('aliases') or [])]); return x[1] if x else None
def ruleok(r,e):
 b,s=blob(e),stage(e)
 if r.get('stage_any') and not has(s,r['stage_any']): return False
 if r.get('blob_any') and not has(b,r['blob_any']): return False
 if r.get('exclude_any') and has(b,r['exclude_any']): return False
 return True
def classify(q,e):
 i=intent(q); f=family(q)
 terms=[q]
 if i: terms += [i.get('canonical',''),*(i.get('aliases') or [])]
 x=n(' '.join([*(e.get('explicit') or []),*evidence(e)]))
 if has(x,terms): return 'A'
 y=n(' '.join(map(str,e.get('inferred') or [])))
 if has(y,terms): return 'B'
 p=i.get('profile') if i else (RULES.get('fallback_profiles',{}).get(f.get('id')) if f else None)
 for r in RULES.get('profiles',{}).get(p,{}).get('rules',[]):
  if ruleok(r,e): return r.get('level','C')
 if n(q) and n(q) in blob(e): return 'B'
 return None
rows=[]; result_sets={}
for q in QUERIES:
 counts={'A':0,'B':0,'C':0}; ids=[]
 for idx,e in enumerate(EV):
  lv=classify(q,e)
  if lv:
   counts[lv]+=1; ids.append(idx)
 total=sum(counts.values()); result_sets[q]=set(ids)
 rows.append({'query':q,'family':(family(q) or {}).get('id'),'intent':(intent(q) or {}).get('id'),'A':counts['A'],'B':counts['B'],'C':counts['C'],'total':total,'match_rate':round(total/max(1,len(EV)),4),'high_confidence_rate':round((counts['A']+counts['B'])/max(1,len(EV)),4)})
zero=[r for r in rows if r['total']==0]
broad=[r for r in rows if r['match_rate']>.60]
high_broad=[r for r in rows if r['high_confidence_rate']>.50]
counts=[r['total'] for r in rows]
# Cross-family near-duplicate result sets are suspicious because unrelated products should not return almost the same companies.
sim=[]
for a,b in itertools.combinations(rows,2):
 if a['family']==b['family'] or not a['family'] or not b['family']: continue
 sa,sb=result_sets[a['query']],result_sets[b['query']]
 if not sa or not sb: continue
 j=len(sa&sb)/len(sa|sb)
 if j>=.85: sim.append({'a':a['query'],'b':b['query'],'family_a':a['family'],'family_b':b['family'],'jaccard':round(j,4),'a_count':len(sa),'b_count':len(sb)})
# Generic new-factory anti-pollution probe across the exact 60 user-facing queries.
GEN={'company':'測試','stage':'新廠動土','industry':'一般製造','title':'一般製造業新廠動土','explicit':[],'inferred':[],'explicit_evidence':{}}
generic=[q for q in QUERIES if classify(q,GEN)]
generic_hi=[q for q in QUERIES if classify(q,GEN) in ('A','B')]
report={
 'version':'SEARCH_QUALITY_AUDIT_V1',
 'events':len(EV),'queries':len(QUERIES),
 'zero_result_count':len(zero),'zero_result_rate':round(len(zero)/len(QUERIES),4),'zero_queries':[r['query'] for r in zero],
 'median_result_count':statistics.median(counts),'mean_result_count':round(statistics.mean(counts),2),'max_result_count':max(counts) if counts else 0,
 'broad_over_60pct_count':len(broad),'broad_over_60pct_queries':[r['query'] for r in broad],
 'high_confidence_over_50pct_count':len(high_broad),'high_confidence_over_50pct_queries':[r['query'] for r in high_broad],
 'generic_new_factory_match_count':len(generic),'generic_new_factory_match_rate':round(len(generic)/len(QUERIES),4),
 'generic_new_factory_high_count':len(generic_hi),'generic_new_factory_high_rate':round(len(generic_hi)/len(QUERIES),4),
 'cross_family_jaccard_ge_085_count':len(sim),'cross_family_jaccard_ge_085':sim[:30],
 'query_rows':rows
}
# Initial commercial gate: broad coverage is useful, but zero-result and all-company pollution are not.
checks={
 'zero_result_rate_le_20pct': report['zero_result_rate']<=.20,
 'generic_match_rate_le_45pct': report['generic_new_factory_match_rate']<=.45,
 'generic_high_rate_le_35pct': report['generic_new_factory_high_rate']<=.35,
 'broad_query_share_le_10pct': len(broad)/len(QUERIES)<=.10,
 'high_confidence_broad_share_le_10pct': len(high_broad)/len(QUERIES)<=.10,
 'cross_family_near_duplicate_pairs_le_6': len(sim)<=6
}
report['checks']=checks
report['verdict']='PASS_REAL_EVENT_SEARCH_QUALITY_V1' if all(checks.values()) else 'FAIL_REAL_EVENT_SEARCH_QUALITY_V1'
(R/'search_quality_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='query_rows'},ensure_ascii=False,indent=2))
print(report['verdict'])
