#!/usr/bin/env python3
"""SHADOW full-market Shioaji contract universe discovery, no orders or quotes.
Outputs only aggregate counts and bounded sample codes, not licensed bars.
"""
import json,os,sys,time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import shioaji as sj

def main():
    key=os.getenv("SHIOAJI_API_KEY");secret=os.getenv("SHIOAJI_SECRET_KEY")
    if not key or not secret:print("HOLD: secrets missing");return 2
    api=sj.Shioaji(simulation=False)
    try:
        api.login(api_key=key,secret_key=secret,subscribe_trade=False)
        stocks=api.Contracts.Stocks
        items=[]
        for exchange in ("TSE","OTC"):
            try: contracts=list(stocks[exchange])
            except Exception as exc:
                print("HOLD:",exchange,"contract enumeration:",type(exc).__name__);return 3
            selected=[]
            for contract in contracts:
                code=str(getattr(contract,"code",""))
                if len(code)==4 and code.isdigit():
                    selected.append(code)
            items.append({"exchange":exchange,"total_contracts":len(contracts),"four_digit_codes":len(set(selected)),"sample":sorted(set(selected))[:5]})
        summary={"date_utc":datetime.now(timezone.utc).date().isoformat(),"status":"PASS_DISCOVERY_SHADOW" if all(x["four_digit_codes"]>0 for x in items) else "HOLD","markets":items,"data_exported":False,"orders_placed":False}
        Path("full_market_universe_discovery_shadow.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(summary,ensure_ascii=False))
        return 0 if summary["status"]=="PASS_DISCOVERY_SHADOW" else 3
    except Exception as exc:
        print("FAIL: universe discovery",type(exc).__name__);return 1
    finally:
        try:api.logout()
        except Exception:pass
if __name__=="__main__":sys.exit(main())
