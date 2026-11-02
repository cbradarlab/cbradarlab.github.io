#!/usr/bin/env python3
"""Offline deterministic checks for private SHADOW sector aggregator."""
from shadow_sector_minute_aggregate import build, minute
assert minute('1793350860000000000') == '09:01'

master={"stocks":[{"id":"1101","industry":"01"},{"id":"1102","industry":"01"},{"id":"2330","industry":"24"}]}
data={"date":"2026-11-02","generated_at":"test","stocks":[
 {"code":"1101","minutes":[{"t":"2026-11-02 09:00","c":10,"v":100},{"t":"2026-11-02 09:02","c":11,"v":50}]},
 {"code":"1102","minutes":[{"t":"2026-11-02 09:01","c":20,"v":10},{"t":"2026-11-02 09:02","c":18,"v":10}]},
 {"code":"2330","minutes":[{"t":"2026-11-02 09:00","c":100,"v":1}]}
]}
r=build(data,master)
assert [f["time"] for f in r["frames"]]==["09:00","09:01","09:02"]
a=r["frames"][-1]["industries"]
assert a[0]["industry"]=="01" and a[0]["sample_stocks"]==2
assert a[0]["strength"]==0.0 and a[0]["activity"]==170.0
assert a[1]["industry"]=="24" and a[1]["activity"]==1.0
assert r["publish_permitted"] is False and r["production_ready"] is False
print("PASS: 3 timestamps, 2 industries, forward fill, cumulative volume, private-only")
