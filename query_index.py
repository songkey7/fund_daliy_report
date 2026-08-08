import sys
import os
import akshare as ak
import pandas as pd
import requests
from datetime import datetime, timedelta

PUSHPLUS_TOKEN = 'afe064ab9d6f4db1b0aac211555d54e3'

INDEX_LIST = [
    {'name': '上证指数', 'source': 'tx', 'symbol': 'sh000001'},
    {'name': '上证50', 'source': 'tx', 'symbol': 'sh000016'},
    {'name': '沪深300', 'source': 'tx', 'symbol': 'sh000300'},
    {'name': '中证A500', 'source': 'tx', 'symbol': 'sh000510'},
    {'name': '中证500', 'source': 'tx', 'symbol': 'sh000905'},
    {'name': '中证1000', 'source': 'tx', 'symbol': 'sh000852'},
    {'name': '创业板指', 'source': 'tx', 'symbol': 'sz399006'},
    {'name': '科创50', 'source': 'tx', 'symbol': 'sh000688'},
    {'name': '恒生科技', 'source': 'hk', 'symbol': 'HSTECH'},
    {'name': '标普500', 'source': 'us', 'symbol': '.INX'},
    {'name': '纳斯达克100', 'source': 'us', 'symbol': '.NDX'},
    {'name': '黄金', 'source': 'gold', 'symbol': None},
    {'name': '白银', 'source': 'silver', 'symbol': None},
    {'name': '美元/人民币', 'source': 'fx', 'symbol': '美元'},
    {'name': '欧元/人民币', 'source': 'fx', 'symbol': '欧元'},
    {'name': '日元/人民币', 'source': 'fx', 'symbol': '日元'},
    {'name': '英镑/人民币', 'source': 'fx', 'symbol': '英镑'},
    {'name': '港元/人民币', 'source': 'fx', 'symbol': '港元'},
    {'name': '澳元/人民币', 'source': 'fx', 'symbol': '澳元'},
]


def query_tx(symbol):
    df = ak.stock_zh_index_daily_tx(symbol=symbol)
    df['date'] = pd.to_datetime(df['date'])
    df = df.rename(columns={'close': 'price'})
    return df.sort_values('date', ascending=False).reset_index(drop=True)


def query_hk(symbol):
    df = ak.stock_hk_index_daily_sina(symbol=symbol)
    df['date'] = pd.to_datetime(df['date'])
    df = df.rename(columns={'close': 'price'})
    return df.sort_values('date', ascending=False).reset_index(drop=True)


def query_us(symbol):
    df = ak.index_us_stock_sina(symbol=symbol)
    df['date'] = pd.to_datetime(df['date'])
    df = df.rename(columns={'close': 'price'})
    return df.sort_values('date', ascending=False).reset_index(drop=True)


_FX_DF = None


def query_fx(symbol):
    global _FX_DF
    if _FX_DF is None:
        df = ak.currency_boc_safe()
        df['date'] = pd.to_datetime(df['日期'])
        _FX_DF = df
    df = _FX_DF.copy()
    df['price'] = df[symbol].astype(float)
    if symbol != '日元':
        df['price'] = df['price'] / 100
    return df.sort_values('date', ascending=False).reset_index(drop=True)


QUERY_MAP = {'tx': query_tx, 'hk': query_hk, 'us': query_us, 'fx': query_fx}


def query_gold():
    df = ak.futures_zh_daily_sina(symbol='AU0')
    df['price'] = df['close'].astype(float)
    df['date'] = pd.to_datetime(df['date'])
    return df.sort_values('date', ascending=False).reset_index(drop=True)


def query_silver():
    df = ak.futures_zh_daily_sina(symbol='AG0')
    df['price'] = df['close'].astype(float)
    df['date'] = pd.to_datetime(df['date'])
    return df.sort_values('date', ascending=False).reset_index(drop=True)


QUERY_MAP_SPECIAL = {'gold': query_gold, 'silver': query_silver}


def calc_return(df, lookback_days):
    if df is None or df.empty:
        return None
    data = df.sort_values('date', ascending=False).reset_index(drop=True)
    try:
        latest = float(data['price'].iloc[0])
    except (IndexError, ValueError):
        return None
    if latest == 0:
        return None
    idx = min(lookback_days, len(data) - 1)
    base = float(data['price'].iloc[idx])
    if base == 0:
        return None
    return round((latest - base) / base * 100, 2)


def calc_ytd_return(df):
    if df is None or df.empty:
        return None
    data = df.sort_values('date', ascending=False).reset_index(drop=True)
    latest = float(data['price'].iloc[0])
    this_year = data['date'].iloc[0].year
    start_date = pd.Timestamp(year=this_year, month=1, day=1)
    before = data[data['date'] <= start_date]
    if before.empty:
        return None
    base = float(before['price'].iloc[0])
    if base == 0:
        return None
    return round((latest - base) / base * 100, 2)


def val_str(v):
    if v is None:
        return '-', ''
    cls = 'pos' if v >= 0 else 'neg'
    return f'{v:+.2f}%', cls


def send_pushplus(token, title, content):
    url = "https://www.pushplus.plus/send"
    req_data = {"token": token, "title": title, "content": content, "template": "html"}
    try:
        resp = requests.post(url, json=req_data, timeout=10)
        return resp.json().get("code") == 200
    except Exception:
        return False


def main():
    results = []

    for idx_info in INDEX_LIST:
        name = idx_info['name']
        source = idx_info['source']
        symbol = idx_info['symbol']

        query_func = QUERY_MAP.get(source) or QUERY_MAP_SPECIAL.get(source)
        try:
            if source in QUERY_MAP_SPECIAL:
                df = query_func()
            else:
                df = query_func(symbol)
        except Exception as e:
            print(f"[{name}] query error: {e}", file=sys.stderr)
            continue

        if df is None or df.empty:
            continue

        item = {
            'name': name,
            'source': source,
            'latest_date': df['date'].iloc[0],
            'price': df['price'].iloc[0],
            'dod': calc_return(df, 1),
            'wow': calc_return(df, 5),
            'mom': calc_return(df, 22),
            'yoy': calc_return(df, 252),
            'ytd': calc_ytd_return(df),
        }
        results.append(item)
        print(f"[{name}] {item['price']:.0f} | {item['latest_date'].strftime('%Y-%m-%d')}", file=sys.stderr)

    if not results:
        return

    # ====== Terminal ======
    sep = "-" * 130
    print(sep)
    print(f"{'指数':<12} {'日期':<12} {'点位':>12} {'日涨跌':>8} {'WoW':>8} {'MoM':>8} {'YoY':>8} {'YTD':>8}")
    print(sep)
    for item in results:
        dod, _ = val_str(item['dod'])
        wow, _ = val_str(item['wow'])
        mom, _ = val_str(item['mom'])
        yoy, _ = val_str(item['yoy'])
        ytd, _ = val_str(item['ytd'])
        price_str = f"{item['price']:.0f}" if item['source'] != 'fx' else f"{item['price']:.2f}"
        print(
            f"{item['name']:<12} "
            f"{item['latest_date'].strftime('%Y-%m-%d'):<12} "
            f"{price_str:>12}  "
            f"{dod:>8}  {wow:>8}  {mom:>8}  {yoy:>8}  {ytd:>8}"
        )
    print(sep)

    # ====== HTML ======
    now_str = datetime.now().strftime('%Y%m%d')
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')

    style = """
    <meta name='viewport' content='width=device-width,initial-scale=1,maximum-scale=1'>
    <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    body { font-family:-apple-system; background:#f5f5f5; padding:12px 8px 24px; -webkit-text-size-adjust:100%; }
    .report-title { font-size:20px; font-weight:800; color:#1a1a1a; text-align:center; padding:10px 0 4px; }
    .report-date { font-size:12px; color:#999; text-align:center; margin-bottom:12px; }
    .section-title { font-size:14px; font-weight:700; color:#555; margin:12px 0 6px 4px; padding-left:4px; border-left:3px solid #4a90d9; }
    table { width:100%; border-collapse:collapse; background:white; border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.06); }
    th { background:#f0f3f8; color:#666; font-size:11px; font-weight:600; padding:8px 4px; text-align:center; white-space:nowrap; }
    th:first-child { text-align:left; padding-left:10px; }
    td { font-size:12px; padding:7px 4px; text-align:center; border-bottom:1px solid #f0f0f0; white-space:nowrap; }
    td:first-child { font-weight:600; text-align:left; padding-left:10px; color:#222; }
    td.price { font-weight:700; color:#333; }
    .pos { color:#e74c3c; font-weight:600; }
    .neg { color:#27ae60; font-weight:600; }
    .footer { text-align:center; color:#bbb; font-size:12px; margin-top:16px; padding:8px; }
    </style>
    """

    content = f"<html><head><meta charset='utf-8'>{style}</head><body>"
    content += f"<div class='report-title'>大盘宽基指数</div>"
    content += f"<div class='report-date'>{ts}</div>"

    a_indices = [r for r in results if r['source'] in ('tx',)]
    hk_us = [r for r in results if r['source'] in ('hk', 'us')]
    commodity = [r for r in results if r['source'] in ('gold', 'silver')]
    fx_list = [r for r in results if r['source'] in ('fx',)]

    header = "<tr><th>指数</th><th>最新</th><th>日涨跌</th><th>WoW</th><th>MoM</th><th>YoY</th><th>YTD</th></tr>"

    for title, group in [("A股", a_indices), ("境外", hk_us), ("商品", commodity), ("汇率", fx_list)]:
        content += f"<div class='section-title'>{title}</div>"
        content += f"<table>{header}<tbody>"
        for item in group:
            dod, dc = val_str(item['dod'])
            wow, wc = val_str(item['wow'])
            mom, mc = val_str(item['mom'])
            yoy, yc = val_str(item['yoy'])
            ytd, ytc = val_str(item['ytd'])
            content += f"<tr>"
            content += f"<td>{item['name']}</td>"
            price_html = f"{item['price']:.0f}" if item['source'] != 'fx' else f"{item['price']:.2f}"
            content += f"<td class='price'>{price_html}</td>"
            content += f"<td class='{dc}'>{dod}</td>"
            content += f"<td class='{wc}'>{wow}</td>"
            content += f"<td class='{mc}'>{mom}</td>"
            content += f"<td class='{yc}'>{yoy}</td>"
            content += f"<td class='{ytc}'>{ytd}</td>"
            content += f"</tr>"
        content += "</tbody></table>"

    content += f"<div class='footer'>生成于 {ts}</div>"
    content += "</body></html>"

    if os.environ.get('GITHUB_ACTIONS'):
        ok = send_pushplus(PUSHPLUS_TOKEN, f"指数日报 {now_str}", content)
        print(f"\nPushPlus 推送{'成功' if ok else '失败'}")
    else:
        print("\n本地运行，跳过推送")

    with open('preview_index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("已保存 preview_index.html")


if __name__ == '__main__':
    main()
