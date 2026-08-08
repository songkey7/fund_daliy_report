import sys
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


QUERY_MAP = {'tx': query_tx, 'hk': query_hk, 'us': query_us}


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

        query_func = QUERY_MAP[source]
        try:
            df = query_func(symbol)
        except Exception as e:
            print(f"[{name}] query error: {e}", file=sys.stderr)
            continue

        if df is None or df.empty:
            continue

        item = {
            'name': name,
            'latest_date': df['date'].iloc[0],
            'price': df['price'].iloc[0],
            'dod': calc_return(df, 1),
            'wow': calc_return(df, 5),
            'mom': calc_return(df, 22),
            'yoy': calc_return(df, 252),
            'ytd': calc_ytd_return(df),
        }
        results.append(item)
        print(f"[{name}] {item['price']:.2f} | {item['latest_date'].strftime('%Y-%m-%d')}", file=sys.stderr)

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
        print(
            f"{item['name']:<12} "
            f"{item['latest_date'].strftime('%Y-%m-%d'):<12} "
            f"{item['price']:>12.2f}  "
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
    .index-card { background:white; border-radius:14px; padding:14px; margin:8px 0; box-shadow:0 2px 8px rgba(0,0,0,0.06); }
    .index-card .header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px; }
    .index-card .name { font-size:16px; font-weight:700; color:#1a1a1a; }
    .index-card .price-info { text-align:right; }
    .index-card .price-val { font-size:20px; font-weight:700; color:#333; }
    .index-card .grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px 4px; }
    .index-card .grid .cell { text-align:center; padding:4px 2px; background:#f8f9fa; border-radius:8px; line-height:1.5; }
    .index-card .grid .cell .label { color:#888; font-size:10px; }
    .value { font-size:13px; font-weight:700; }
    .value.pos { color:#e74c3c; }
    .value.neg { color:#27ae60; }
    .footer { text-align:center; color:#bbb; font-size:12px; margin-top:16px; padding:8px; }
    </style>
    """

    content = f"<html><head><meta charset='utf-8'>{style}</head><body>"
    content += f"<div class='report-title'>大盘宽基指数</div>"
    content += f"<div class='report-date'>{ts}</div>"

    # Separate A股 and 境外
    a_indices = [r for r in results if r['name'] not in ('恒生科技', '标普500', '纳斯达克100')]
    overseas = [r for r in results if r['name'] in ('恒生科技', '标普500', '纳斯达克100')]

    for group in (a_indices, overseas):
        for item in group:
            dod_str, dod_cls = val_str(item['dod'])

            metrics = [
                ('日涨跌', item['dod']),
                ('WoW', item['wow']),
                ('MoM', item['mom']),
                ('YoY', item['yoy']),
                ('YTD', item['ytd']),
            ]

            metric_html = ''
            for label, v in metrics:
                s, cls = val_str(v)
                metric_html += f"<div class='cell'><span class='label'>{label}</span><br><span class='value {cls}'>{s}</span></div>"

            content += f"""<div class="index-card">
            <div class="header">
            <div class="name">{item['name']}</div>
            <div class="price-info"><div class="price-val">{item['price']:,.2f}</div><div class="value {dod_cls}" style="font-size:13px;">{dod_str}</div></div>
            </div>
            <div class="grid">{metric_html}</div></div>"""

    content += f"<div class='footer'>生成于 {ts}</div>"
    content += "</body></html>"

    ok = send_pushplus(PUSHPLUS_TOKEN, f"指数日报 {now_str}", content)
    print(f"\nPushPlus 推送{'成功' if ok else '失败'}")

    with open('preview_index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("已保存 preview_index.html")


if __name__ == '__main__':
    main()
