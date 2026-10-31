#!/usr/bin/env python3
"""SHADOW-only Shioaji cloud login probe. No orders, no quotes, no credential output."""
import os, sys
try:
    import shioaji as sj
    key=os.environ.get("SHIOAJI_API_KEY","")
    secret=os.environ.get("SHIOAJI_SECRET_KEY","")
    if not key or not secret:
        print("HOLD: missing GitHub Actions secrets"); sys.exit(2)
    api=sj.Shioaji(simulation=False)
    try:
        api.login(api_key=key,secret_key=secret,subscribe_trade=False)
        print("PASS: Shioaji cloud login succeeded (no order, no market data exported)")
    finally:
        try: api.logout()
        except Exception: pass
except Exception as exc:
    print("FAIL: cloud login or environment issue: "+type(exc).__name__)
    sys.exit(1)
