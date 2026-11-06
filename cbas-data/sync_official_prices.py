"""Public official CB close-only snapshot for private CBAS P&L viewer."""
import csv
import datetime as dt
import io
import json
import pathlib
import re
import urllib.request
from zoneinfo import ZoneInfo

OUT = pathlib.Path('cbas-data/official_prices_latest.json')
TODAY = dt.datetime.now(ZoneInfo('Asia/Taipei')).date()


def parse(raw, ymd, url):
    text = raw.decode('big5', errors='replace')
    rows = list(csv.reader(io.StringIO(text)))
    header = next((row for row in rows if row and row[0] == 'DATADATE'), [])
    roc = int(ymd[:4]) - 1911
    expected = f'{roc}年{int(ymd[4:6])}月{int(ymd[6:])}日'
    if expected not in ''.join(header).replace(' ', ''):
        raise ValueError('官方資料日期不符或回傳非 CSV')
    prices = {}
    for row in rows:
        if len(row) < 5 or row[0] != 'BODY' or not re.fullmatch(r'\d{5,6}', row[1]):
            continue
        if row[3] != '等價':
            continue
        rawprice = row[4].strip().replace(',', '')
        try:
            price = float(rawprice) if rawprice else None
        except ValueError:
            price = None
        has_trade = price is not None and 0 < price < 10000
        prices[row[1]] = dict(price=price if has_trade else None,
                              hasTrade=has_trade,
                              priceType='officialClose' if has_trade else 'noTrade',
                              tradeDate=ymd)
    if len(prices) < 250:
        raise ValueError(f'官方全市場筆數不足: {len(prices)}')
    return dict(tradeDate=ymd, rows=len(prices), sourceUrl=url, prices=prices)


def main():
    errors = []
    for back in range(7):
        ymd = (TODAY - dt.timedelta(days=back)).strftime('%Y%m%d')
        url = (f'https://www.tpex.org.tw/storage/bond_zone/tradeinfo/cb/'
               f'{ymd[:4]}/{ymd[:6]}/RSta0113.{ymd}-C.csv')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 CBAS-SHADOW'})
            with urllib.request.urlopen(req, timeout=14) as res:
                report = parse(res.read(), ymd, url)
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(report, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
            print(f'PASS {ymd}: {report["rows"]} official CB rows, {sum(q["hasTrade"] for q in report["prices"].values())} traded')
            return
        except Exception as exc:
            errors.append(f'{ymd}: {type(exc).__name__}: {exc}')
    raise RuntimeError('FAIL: no verified official report. Preserved old snapshot. ' + '; '.join(errors))


if __name__ == '__main__':
    main()
