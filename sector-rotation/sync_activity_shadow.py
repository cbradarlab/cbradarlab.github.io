#!/usr/bin/env python3
"""Official TWSE + TPEx close turnover, separate SHADOW research snapshot."""
import csv
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
TWSE = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
OUTPUT = DATA / "sector_activity_latest_shadow.json"
HISTORY = DATA / "sector_activity_history_shadow.json"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SectorRotationShadow/1.0"})
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.load(response)


def ymd(value):
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 7:  # ROC 1151102
        return f"{int(digits[:3]) + 1911:04d}-{digits[3:5]}-{digits[5:7]}"
    if len(digits) == 8 and digits.startswith("20"):
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    raise ValueError(f"Unrecognized source date: {value!r}")


def amount(value):
    raw = str(value).replace(",", "").strip()
    if not raw or raw in ("--", "-", "N/A"):
        return None
    return int(float(raw))


def main():
    master = json.loads((DATA / "stocks.json").read_text(encoding="utf-8"))
    labels = json.loads((DATA / "official_industry_labels.json").read_text(encoding="utf-8"))["labels"]
    stocks = {(("上市" if s["market"] == "上市" else "上櫃"), str(s["id"])): s
              for s in master["stocks"]}
    sources = [
        ("上市", TWSE, "Code", "TradeValue"),
        ("上櫃", TPEX, "SecuritiesCompanyCode", "TransactionAmount"),
    ]
    found = {}
    dates = {}
    ignored = 0
    for market, url, id_key, value_key in sources:
        rows = get_json(url)
        if not isinstance(rows, list) or len(rows) < 500:
            raise ValueError(f"{market}: unexpected response size")
        ds = set()
        matched = 0
        for row in rows:
            symbol = str(row.get(id_key, "")).strip()
            stock = stocks.get((market, symbol))
            if stock is None:
                ignored += 1
                continue
            value = amount(row.get(value_key))
            if value is None or value < 0:
                continue
            d = ymd(row.get("Date"))
            ds.add(d)
            key = (market, symbol)
            if key in found:
                raise ValueError(f"{market}: duplicate stock {symbol}")
            found[key] = (stock["industry"], value)
            matched += 1
        if len(ds) != 1:
            raise ValueError(f"{market}: mixed or missing quote dates {sorted(ds)}")
        dates[market] = ds.pop()
        if matched < 500:
            raise ValueError(f"{market}: too few matched equities ({matched})")
    if len(set(dates.values())) != 1:
        raise ValueError(f"TWSE/TPEx dates mismatch: {dates}")
    if len(found) / len(stocks) < .90:
        raise ValueError(f"Insufficient stock coverage: {len(found)}/{len(stocks)}")

    groups = defaultdict(lambda: {"ntd": 0, "stocks": 0, "上市": 0, "上櫃": 0})
    for (market, _symbol), (industry, value) in found.items():
        g = groups[industry]
        g["ntd"] += value
        g["stocks"] += 1
        g[market] += value
    total = sum(row["ntd"] for row in groups.values())
    industries = [
        {"code": code, "name": labels.get(code, f"未確認產業 {code}"),
         "ntd": g["ntd"], "stock_count": g["stocks"],
         "twse_ntd": g["上市"], "tpex_ntd": g["上櫃"],
         "share_pct": round(100 * g["ntd"] / total, 3)}
        for code, g in groups.items() if g["stocks"]
    ]
    industries.sort(key=lambda g: g["ntd"], reverse=True)
    # Existing reviewed memberships are user-project data, not scraped directory copies.
    taxonomy = json.loads((DATA / "sector_taxonomy.json").read_text(encoding="utf-8"))
    panel_names = {"industry_chain": taxonomy["industry_chain"],
                   "concept": taxonomy["concepts"]}
    panel_values = {kind: {name: {"ntd": 0, "stock_count": 0, "mapped_count": 0}
                           for name in names} for kind, names in panel_names.items()}
    seen_memberships = set()
    with (DATA / "stock_panel_memberships.csv").open(encoding="utf-8-sig",
                                                     newline="") as handle:
        for row in csv.DictReader(handle):
            kind, panel = row["kind"], row["panel"]
            if kind not in panel_values or panel not in panel_values[kind]:
                raise ValueError(f"Unrecognized reviewed panel: {kind}/{panel}")
            key = (row["market"], row["code"], kind, panel)
            if key in seen_memberships:
                raise ValueError(f"Duplicate membership: {key}")
            seen_memberships.add(key)
            p = panel_values[kind][panel]
            p["mapped_count"] += 1
            market = {"TWSE": "上市", "TPEX": "上櫃"}.get(row["market"])
            if market is None:
                raise ValueError(f"Unrecognized member market: {row['market']}")
            quote = found.get((market, row["code"]))
            if quote is not None:
                p["ntd"] += quote[1]
                p["stock_count"] += 1
    panels = {}
    for kind, groups in panel_values.items():
        values = [
            {"name": name, "ntd": (p["ntd"] if p["stock_count"] else None),
             "stock_count": p["stock_count"], "mapped_count": p["mapped_count"],
             "market_share_pct": round(100 * p["ntd"] / total, 3)}
            for name, p in groups.items()
        ]
        values.sort(key=lambda r: (r["ntd"] is None,
                                   -(r["ntd"] or 0), r["name"]))
        panels[kind] = {
            "total_groups": len(groups),
            "mapped_groups": sum(p["mapped_count"] > 0 for p in groups.values()),
            "mapping_type": "official_industry_proxy" if kind == "industry_chain"
                            else "reviewed_examples_only",
            "groups": values,
        }
    day = next(iter(dates.values()))
    result = {
        "schema_version": 1, "status": "SHADOW_CLOSE_ONLY",
        "date": day, "source_dates": dates,
        "source_urls": {"上市": TWSE, "上櫃": TPEX},
        "matched_stocks": len(found), "master_stocks": len(stocks),
        "ignored_non_master_rows": ignored, "total_ntd": total,
        "industries": industries, "panels": panels,
        "note": "成交金額，不是淨流入；只代表已收盤交易日，不是盤中每分鐘資金流。"
    }
    history = []
    if HISTORY.exists():
        history = json.loads(HISTORY.read_text(encoding="utf-8"))
    history = [r for r in history if r.get("date") != day]
    history.append({"date": day, "total_ntd": total,
                    "industries": [{"code": r["code"], "ntd": r["ntd"]}
                                   for r in industries]})
    history.sort(key=lambda r: r["date"])
    history = history[-45:]
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    print(f"PASS date={day} matched={len(found)}/{len(stocks)} "
          f"industries={len(industries)} total_ntd={total} history={len(history)}")


if __name__ == "__main__":
    main()
