#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit whether Opportunity Radar results are usable for research and outreach.

This is diagnostic only: it does not mutate events or search rules and does not fail CI.
"""
from __future__ import annotations
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVENTS = json.loads((ROOT / 'events.json').read_text(encoding='utf-8'))
STATUS = json.loads((ROOT / 'status.json').read_text(encoding='utf-8'))

URL_RE = re.compile(r'(?:https?://|www\.)\S+', re.I)
EMAIL_RE = re.compile(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', re.I)
PHONE_RE = re.compile(r'(?:\+?886[-\s]?)?(?:0\d{1,2}[-\s]?)?\d{3,4}[-\s]?\d{3,4}')


def parse_date(value):
    try:
        return dt.date.fromisoformat(str(value or '')[:10])
    except Exception:
        return None


def route_texts(e):
    out=[]
    for key in (
        'contact','website','company_website','contact_url','procurement_url',
        'phone','email','company_phone','company_email'
    ):
        v=e.get(key)
        if v:
            out.append(str(v).strip())
    return out


def has_real_contact(e):
    # Descriptive text such as "公司名稱已識別" is NOT a contact route.
    # Count only a concrete URL, email address or phone number.
    joined=' '.join(route_texts(e))
    return bool(joined and (URL_RE.search(joined) or EMAIL_RE.search(joined) or PHONE_RE.search(joined)))


def has_verified_route(e):
    return has_real_contact(e)


def pct(n,d):
    return round(n/d,4) if d else 0.0


today=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
total=len(EVENTS)
metrics={
    'company_identified':0,
    'dated':0,
    'official_source_link':0,
    'source_type_present':0,
    'city_present':0,
    'district_present':0,
    'explicit_evidence_present':0,
    'real_contact_present':0,
    'verified_outreach_route_present':0,
    'fresh_90d':0,
    'fresh_180d':0,
    'fresh_365d':0,
    'research_actionable':0,
    'outreach_ready':0,
}
missing_outreach_examples=[]

for e in EVENTS:
    company=bool(str(e.get('company') or '').strip())
    d=parse_date(e.get('date'))
    source=str(e.get('source') or '').strip()
    official_link=source.startswith('http://') or source.startswith('https://')
    source_type=bool(str(e.get('source_type') or '').strip())
    city=bool(str(e.get('city') or '').strip())
    district=bool(str(e.get('district') or '').strip())
    evidence=bool(e.get('explicit_evidence'))
    real_contact=has_real_contact(e)
    route=has_verified_route(e)

    metrics['company_identified']+=company
    metrics['dated']+=bool(d)
    metrics['official_source_link']+=official_link
    metrics['source_type_present']+=source_type
    metrics['city_present']+=city
    metrics['district_present']+=district
    metrics['explicit_evidence_present']+=evidence
    metrics['real_contact_present']+=real_contact
    metrics['verified_outreach_route_present']+=route

    if d:
        age=(today-d).days
        metrics['fresh_90d']+=0<=age<=90
        metrics['fresh_180d']+=0<=age<=180
        metrics['fresh_365d']+=0<=age<=365

    research_ok=company and bool(d) and official_link and source_type
    outreach_ok=research_ok and route
    metrics['research_actionable']+=research_ok
    metrics['outreach_ready']+=outreach_ok

    if research_ok and not outreach_ok and len(missing_outreach_examples)<12:
        missing_outreach_examples.append({
            'company':e.get('company'),
            'date':e.get('date'),
            'city':e.get('city'),
            'source_type':e.get('source_type'),
            'contact':e.get('contact'),
        })

rates={k+'_rate':pct(v,total) for k,v in metrics.items()}
research_rate=rates['research_actionable_rate']
outreach_rate=rates['outreach_ready_rate']
if research_rate>=0.95 and outreach_rate>=0.70:
    verdict='PASS_ACTIONABILITY_V1_OUTREACH_READY'
elif research_rate>=0.95:
    verdict='PASS_RESEARCH_ACTIONABLE__OUTREACH_ENRICHMENT_NEEDED'
else:
    verdict='FAIL_RESEARCH_ACTIONABILITY_V1'

report={
    'version':'OPPORTUNITY_ACTIONABILITY_AUDIT_V1_2_ENRICHED_ROUTE_FIELDS',
    'generated_at':dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='seconds'),
    'events':total,
    'source_status':STATUS.get('source_status'),
    'metrics':metrics,
    'rates':rates,
    'thresholds':{
        'research_actionable_pass':0.95,
        'outreach_ready_pass':0.70,
    },
    'definitions':{
        'research_actionable':'company + valid date + source URL + source_type',
        'outreach_ready':'research_actionable + concrete URL/email/phone route',
        'descriptive_contact_text_is_not_ready':True,
    },
    'missing_outreach_examples':missing_outreach_examples,
    'verdict':verdict,
}
(ROOT/'actionability_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
print(verdict)
