import sys
import os
import re
import json
import akshare as ak
import pandas as pd
import requests
from datetime import datetime, timedelta

PUSHPLUS_TOKEN = 'afe064ab9d6f4db1b0aac211555d54e3'

INDEX_LIST = [
    {'name': '上证指数', 'source': 'tx', 'symbol': 'sh000001', 'pei_code': '000001'},
    {'name': '上证50', 'source': 'tx', 'symbol': 'sh000016', 'etf_code': 'SSE/000016'},
    {'name': '沪深300', 'source': 'tx', 'symbol': 'sh000300', 'etf_code': 'SSE/000300'},
    {'name': '中证A500', 'source': 'tx', 'symbol': 'sh000510', 'etf_code': 'SSE/000510'},
    {'name': '中证500', 'source': 'tx', 'symbol': 'sh000905', 'etf_code': 'SSE/000905'},
    {'name': '中证1000', 'source': 'tx', 'symbol': 'sh000852', 'etf_code': 'SSE/000852'},
    {'name': '创业板指', 'source': 'tx', 'symbol': 'sz399006', 'etf_code': 'SZSE/399006'},
    {'name': '科创50', 'source': 'tx', 'symbol': 'sh000688', 'etf_code': 'SSE/000688'},
    {'name': '中证红利', 'source': 'tx', 'symbol': 'sh000922', 'etf_code': 'CSI/000922'},
    {'name': '中证红利低波', 'source': 'tx', 'symbol': 'sh512890', 'scale_from': 'H30269', 'etf_code': 'CSI/H30269'},
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


def query_em(symbol):
    df = ak.stock_zh_index_daily_em(symbol=symbol)
    df['date'] = pd.to_datetime(df['date'])
    df = df.rename(columns={'close': 'price'})
    return df.sort_values('date', ascending=False).reset_index(drop=True)


QUERY_MAP = {'tx': query_tx, 'hk': query_hk, 'us': query_us, 'fx': query_fx, 'em': query_em}


def query_gold():
    df = ak.spot_hist_sge(symbol='Au99.99')
    df['price'] = df['close'].astype(float)
    df['date'] = pd.to_datetime(df['date'])
    return df.sort_values('date', ascending=False).reset_index(drop=True)


def query_silver():
    df = ak.spot_hist_sge(symbol='Ag99.99')
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


_CSI_DF = None
_PE_CACHE = {}


def _get_pe_from_etf_run(idx_info):
    cache_key = idx_info.get('etf_code') or idx_info.get('pei_code')
    if cache_key in _PE_CACHE:
        return _PE_CACHE[cache_key]

    pe = None
    pct = None
    etf_code = idx_info.get('etf_code')
    if etf_code:
        try:
            url = f"https://www.etf.run/index/{etf_code}"
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)

            m = re.search(r'PE[：:](\d+\.?\d*)', r.text)
            if m:
                pe = round(float(m.group(1)), 2)

            scripts = re.findall(r'<script[^>]*>(.*?)</script>', r.text, re.DOTALL)
            for s in scripts:
                if 'historyPePercentile' not in s:
                    continue
                clean = s.replace(r'\"', '"')
                cols_m = re.search(r'"fieldNames":(\[[^\]]+historyPePercentile[^\]]+\])', clean)
                if not cols_m:
                    continue
                cols = json.loads(cols_m.group(1))
                idx = cols.index('historyPePercentile')
                tail = clean[cols_m.end():]
                vals_m = re.search(r'"values":(\[\[)', tail)
                if not vals_m:
                    continue
                pos = cols_m.end() + vals_m.start() + len('"values":')
                depth = 0
                for i in range(pos, len(clean)):
                    if clean[i] == '[':
                        depth += 1
                    elif clean[i] == ']':
                        depth -= 1
                        if depth == 0:
                            rows = json.loads(clean[pos:i+1])
                            last = rows[-1]
                            if idx < len(last) and last[idx] is not None:
                                pct = round(float(last[idx]) * 100, 0)
                            break
                break
        except Exception:
            pass

    if pe is None:
        pei_code = idx_info.get('pei_code')
        if pei_code:
            try:
                df = ak.stock_zh_index_value_csindex(symbol=pei_code)
                pe = round(float(df['市盈率1'].iloc[-1]), 2)
            except Exception:
                pass

    result = {'pe': pe, 'pct': pct}
    _PE_CACHE[cache_key] = result
    return result


def _get_csi_latest():
    global _CSI_DF
    if _CSI_DF is None:
        _CSI_DF = ak.index_csindex_all()
    return _CSI_DF


def _get_scale(csi_code, proxy_price):
    try:
        df = _get_csi_latest()
        row = df[df['指数代码'] == csi_code]
        if row.empty:
            return None
        index_price = float(row['最新收盘'].iloc[0])
        if proxy_price == 0:
            return None
        return index_price / proxy_price
    except Exception:
        return None


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

        if 'scale_from' in idx_info:
            scale = _get_scale(idx_info['scale_from'], df['price'].iloc[0])
            if scale:
                df['price'] = df['price'] * scale

        pe_data = _get_pe_from_etf_run(idx_info) if ('etf_code' in idx_info or 'pei_code' in idx_info) else {'pe': None, 'pct': None}

        item = {
            'name': name,
            'source': source,
            'latest_date': df['date'].iloc[0],
            'price': df['price'].iloc[0],
            'pe': pe_data['pe'],
            'pe_pct': pe_data['pct'],
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
    <meta name='viewport' content='width=device-width,initial-scale=1'>
    <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    body { font-family:-apple-system,'PingFang SC',sans-serif;max-width:480px;color:#222;font-size:14px;line-height:1.6;background:#f0f0f0;padding:12px;margin:0; }
    .header { background:#1a1a2e;color:#fff;padding:12px 16px;border-radius:12px;text-align:center;margin-bottom:10px; }
    .header h1 { font-size:16px;font-weight:600;margin:0; }
    .header .date { font-size:11px;opacity:0.5;margin-top:4px; }
    .section-card { background:#fff;border-radius:10px;padding:14px 16px;margin-bottom:8px;box-shadow:0 1px 2px rgba(0,0,0,0.06); }
    .section-card .title { font-size:13px;font-weight:700;color:#2b4c7e;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #eee; }
    .idx-row { display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid #f6f6f6;font-size:12px; }
    .idx-row:last-child { border-bottom:none; }
    .idx-row .name { font-weight:600;color:#333;flex:0 0 64px; }
    .idx-row .pe { font-weight:600;color:#666;flex:0 0 52px;text-align:right;font-size:11px; }
    .idx-row .price { font-weight:700;color:#333;flex:0 0 50px;text-align:right; }
    .idx-row .returns { display:flex;gap:4px;flex:1;justify-content:flex-end; }
    .idx-row .returns span { width:44px;text-align:center;font-weight:600;font-size:11px; }
    .pos { color:#e53e3e; }
    .neg { color:#38a169; }
    .pe-pct { color:#999;font-size:9px; }
    .col-header { display:flex;justify-content:space-between;align-items:center;padding:4px 0;margin-top:2px;font-size:10px;color:#aaa; }
    .col-header .name { flex:0 0 64px; }
    .col-header .pe { flex:0 0 52px;text-align:right; }
    .col-header .price { flex:0 0 50px;text-align:right; }
    .col-header .returns { display:flex;gap:4px;flex:1;justify-content:flex-end; }
    .col-header .returns span { width:44px;text-align:center; }
    .footer { text-align:center;color:#aaa;font-size:11px;margin-top:12px; }
    </style>
    """

    content = f"<html><head><meta charset='utf-8'>{style}</head><body>"
    content += f"<div class='header'><h1>大盘宽基指数</h1><div class='date'>{ts} 更新</div></div>"

    a_indices = [r for r in results if r['source'] in ('tx', 'em')]
    hk_us = [r for r in results if r['source'] in ('hk', 'us')]
    commodity = [r for r in results if r['source'] in ('gold', 'silver')]
    fx_list = [r for r in results if r['source'] in ('fx',)]

    a_pe_hdr = "<div class='col-header'><span class='name'>指数</span><span class='pe'>PE/分位</span><span class='price'>点位</span><div class='returns'><span>日涨跌</span><span>WoW</span><span>MoM</span><span>YoY</span><span>YTD</span></div></div>"
    no_pe_hdr = "<div class='col-header'><span class='name' style='flex:0 0 80px'>指数</span><span class='price' style='flex:0 0 72px'>点位</span><div class='returns'><span>日涨跌</span><span>WoW</span><span>MoM</span><span>YoY</span><span>YTD</span></div></div>"
    no_pe_name = " style='flex:0 0 80px'"
    no_pe_price = " style='flex:0 0 72px'"

    for title, group in [("A股", a_indices), ("境外", hk_us), ("商品", commodity), ("汇率", fx_list)]:
        show_pe = (title == "A股")
        content += f"<div class='section-card'><div class='title'>{title}</div>"
        content += a_pe_hdr if show_pe else no_pe_hdr
        for item in group:
            dod, dc = val_str(item['dod'])
            wow, wc = val_str(item['wow'])
            mom, mc = val_str(item['mom'])
            yoy, yc = val_str(item['yoy'])
            ytd, ytc = val_str(item['ytd'])
            pe = item.get('pe')
            pe_pct = item.get('pe_pct')
            if pe is not None:
                pe_str = f"{pe:.1f}"
                if pe_pct is not None:
                    pe_str += f"<span class='pe-pct'> {pe_pct:.0f}%</span>"
            else:
                pe_str = '-'
            price_html = f"{item['price']:.0f}" if item['source'] != 'fx' else f"{item['price']:.2f}"
            content += f"<div class='idx-row'>"
            content += f"<span class='name'{no_pe_name if not show_pe else ''}>{item['name']}</span>"
            if show_pe:
                content += f"<span class='pe'>{pe_str}</span>"
            content += f"<span class='price'{no_pe_price if not show_pe else ''}>{price_html}</span>"
            content += f"<div class='returns'>"
            content += f"<span class='{dc}'>{dod}</span>"
            content += f"<span class='{wc}'>{wow}</span>"
            content += f"<span class='{mc}'>{mom}</span>"
            content += f"<span class='{yc}'>{yoy}</span>"
            content += f"<span class='{ytc}'>{ytd}</span>"
            content += f"</div></div>"
        content += "</div>"

    content += f"<div class='footer'>数据来源: 腾讯 · 新浪 · 东方财富 | 仅供参考</div>"
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
