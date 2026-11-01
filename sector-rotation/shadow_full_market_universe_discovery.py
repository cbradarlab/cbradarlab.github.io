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
        # Shioaji has direct code lookup (verified in PCB21); TSE/OTC are not
        # guaranteed dictionary keys. Iterate available contract groups instead.
        try:
            groups=list(stocks)
        except Exception as exc:
            print("HOLD: contract group enumeration:",type(exc).__name__);return 3
        seen={}
        group_stats=[]
        for group in groups:
            try:
                contracts=list(group)
                valid=0
                for contract in contracts:
                    code=str(getattr(contract,"code",""))
                    exchange=str(getattr(contract,"exchange","")).upper()
                    if len(code)==4 and code.isdigit() and exchange in ("TSE","OTC"):
                        seen.setdefault(exchange,set()).add(code)
                        valid+=1
                group_stats.append({"group_type":type(group).__name__,"contracts":len(contracts),"eligible":valid})
            except Exception as exc:
                group_stats.append({"group_type":type(group).__name__,"error":type(exc).__name__})
        for exchange in ("TSE","OTC"):
            selected=sorted(seen.get(exchange,set()))
            items.append({"exchange":exchange,"four_digit_codes":len(selected),"sample":selected[:5]})
        print("GROUP_DIAGNOSTICS",json.dumps(group_stats[:20],ensure_ascii=False))
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
