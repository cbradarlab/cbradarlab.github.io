#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
EVENTS=ROOT/'events.json';OUT=ROOT/'demand_pull_report.json'

def main():
    events=json.loads(EVENTS.read_text(encoding='utf-8'))
    flagged=[e for e in events if e.get('demand_pull') is True]
    bad=[]
    for e in flagged:
        ident=f"{e.get('stock_code','')} {e.get('company','')} {e.get('date','')}"
        if not e.get('stock_code') or not e.get('market'):bad.append([ident,'missing_listed_identity'])
        if not e.get('demand_pull_grade') or not e.get('demand_pull_basis'):bad.append([ident,'missing_grade_or_basis'])
        if e.get('demand_pull_grade')=='AUTO':
            if not e.get('listing_date_at_check'):bad.append([ident,'auto_missing_listing_date'])
            elif str(e.get('listing_date_at_check'))>str(e.get('date','')):bad.append([ident,'auto_later_listing_backfill'])
            if not e.get('demand_pull_demand_term') or not e.get('demand_pull_action_term'):bad.append([ident,'auto_missing_causal_terms'])
    rows=[{'company':e.get('company'),'stock_code':e.get('stock_code'),'date':e.get('date'),'grade':e.get('demand_pull_grade'),'basis':e.get('demand_pull_basis'),'demand_term':e.get('demand_pull_demand_term',''),'action_term':e.get('demand_pull_action_term','')} for e in flagged]
    report={'version':'DEMAND_PULL_AUDIT_V1','events':len(events),'flagged':len(flagged),'bad_count':len(bad),'bad':bad,'rows':rows,'verdict':'PASS' if not bad else 'FAIL'}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    if bad:sys.exit(2)
if __name__=='__main__':main()
