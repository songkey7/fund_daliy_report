import sys
import os
import akshare as ak
import pandas as pd
import requests
from datetime import datetime, timedelta
from collections import defaultdict

POSITION_FILE = 'input/position.txt'
PUSHPLUS_TOKEN = 'afe064ab9d6f4db1b0aac211555d54e3'


def parse_position(filepath):
    positions = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                positions.append({'platform': parts[0], 'code': parts[1]})
    return positions


def get_fund_info(code):
    try:
        df = ak.fund_individual_basic_info_xq(symbol=code)
        if df is not None and not df.empty:
            name_row = df[df['item'] == '基金名称']
            name = name_row['value'].iloc[0] if not name_row.empty else code
            type_row = df[df['item'] == '基金类型']
            ftype = type_row['value'].iloc[0] if not type_row.empty else '-'
            return name, ftype
    except Exception:
        pass

    try:
        df = ak.fund_open_fund_rank_em(symbol='全部')
        match = df[df['基金代码'] == code]
        if not match.empty:
            return match['基金简称'].iloc[0], '-'
    except Exception:
        pass

    return code, '-'


RANK_CACHE = {}

def map_to_rank_category(ftype):
    if '指数' in ftype:
        return '指数型'
    for key in ('债券型', '混合型', '股票型', 'QDII', 'FOF'):
        if key in ftype:
            return key
    return '全部'


RANK_COLUMNS = {
    '近1周': '近1周', '近1月': '近1月', '近3月': '近3月',
    '近6月': '近6月', '近1年': '近1年', '今年来': '今年来',
}


def get_fund_ranks(code, ftype):
    category = map_to_rank_category(ftype)
    for cat in (category, '指数型'):
        if cat not in RANK_CACHE:
            try:
                df = ak.fund_open_fund_rank_em(symbol=cat)
                if df is not None and not df.empty:
                    RANK_CACHE[cat] = df
                else:
                    continue
            except Exception:
                continue
        df = RANK_CACHE[cat]
        match = df[df['基金代码'] == code]
        if match.empty:
            continue
        total = len(df)
        ranks = {}
        for key, col in RANK_COLUMNS.items():
            if col not in df.columns:
                ranks[key] = None
                continue
            sorted_df = df.sort_values(col, ascending=False, na_position='last').reset_index(drop=True)
            pos = sorted_df[sorted_df['基金代码'] == code].index
            if len(pos) > 0:
                ranks[key] = int(pos[0]) + 1
            else:
                ranks[key] = None
        return ranks, total
    return {}, 0


def query_fund_nav(code):
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势", period="成立来")
        if df is None or df.empty:
            return None

        df = df.rename(columns={
            '净值日期': 'date',
            '单位净值': 'nav',
        })
        df['date'] = pd.to_datetime(df['date'])
        df['nav'] = df['nav'].astype(float)
        df = df.sort_values('date', ascending=False).reset_index(drop=True)
        return df
    except Exception as e:
        print(f"[{code}] query nav error: {e}", file=sys.stderr)
        return None


def calc_return(df, lookback_days):
    if df is None or df.empty:
        return None
    data = df.sort_values('date', ascending=False).reset_index(drop=True)
    try:
        latest_nav = float(data['nav'].iloc[0])
    except (IndexError, ValueError):
        return None
    if latest_nav == 0:
        return None

    idx = lookback_days
    if idx >= len(data):
        idx = len(data) - 1
    base_nav = float(data['nav'].iloc[idx])
    if base_nav == 0:
        return None
    return round((latest_nav - base_nav) / base_nav * 100, 2)


def calc_ytd_return(df):
    if df is None or df.empty:
        return None
    data = df.sort_values('date', ascending=False).reset_index(drop=True)
    latest_nav = float(data['nav'].iloc[0])
    this_year = data['date'].iloc[0].year
    start_date = pd.Timestamp(year=this_year, month=1, day=1)
    before = data[data['date'] <= start_date]
    if before.empty:
        return None
    base_nav = float(before['nav'].iloc[0])
    if base_nav == 0:
        return None
    return round((latest_nav - base_nav) / base_nav * 100, 2)


def send_pushplus(token, title, content):
    url = "https://www.pushplus.plus/send"
    req_data = {
        "token": token,
        "title": title,
        "content": content,
        "template": "html"
    }
    try:
        resp = requests.post(url, json=req_data, timeout=10)
        return resp.json().get("code") == 200
    except Exception:
        return False


def val_str(v):
    """Format value with color class: returns (display_str, color_class)"""
    if v is None:
        return '-', ''
    cls = 'pos' if v >= 0 else 'neg'
    return f'{v:+.2f}%', cls


def main():
    positions = parse_position(POSITION_FILE)
    if not positions:
        print("未找到基金持仓数据")
        return

    results = []

    for pos in positions:
        code = pos['code']
        platform = pos['platform']

        name, ftype = get_fund_info(code)
        ranks, rank_total = get_fund_ranks(code, ftype)
        rank_str = f"{ranks.get('近1年', '-')}/{rank_total}" if rank_total > 0 else '-/-'
        print(f"[{code}] {name} | {ftype} | 近1年{rank_str}", file=sys.stderr)

        df = query_fund_nav(code)
        if df is None:
            continue

        item = {
            'code': code,
            'name': name,
            'platform': platform,
            'ftype': ftype,
            'ranks': ranks,
            'rank_total': rank_total,
            'latest_date': df['date'].iloc[0],
            'nav': df['nav'].iloc[0],
            'dod': calc_return(df, 1),
            'wow': calc_return(df, 5),
            'mom': calc_return(df, 22),
            'qoq': calc_return(df, 66),
            'hoh': calc_return(df, 126),
            'yoy': calc_return(df, 252),
            'ytd': calc_ytd_return(df),
        }
        results.append(item)

    if not results:
        return

    # Group by platform
    groups = defaultdict(list)
    for item in results:
        groups[item['platform']].append(item)

    # ====== Terminal output ======
    sep = "-" * 180
    print(sep)
    header = (
        f"{'代码':<8} {'名称':<28} {'日期':<12} {'净值':>10} "
        f"{'日涨跌':>8} {'WoW':>8} {'MoM':>8} {'QoQ':>8} "
        f"{'HoH':>8} {'YoY':>8} {'YTD':>8}"
    )
    print(header)
    print(sep)

    for platform, items in groups.items():
        print(f"\n  【{platform}】")
        for item in items:
            nav_f = f"{item['nav']:10.4f}" if item['nav'] is not None else "    -     "
            dod, _ = val_str(item['dod'])
            wow, _ = val_str(item['wow'])
            mom, _ = val_str(item['mom'])
            qoq, _ = val_str(item['qoq'])
            hoh, _ = val_str(item['hoh'])
            yoy, _ = val_str(item['yoy'])
            ytd, _ = val_str(item['ytd'])

            print(
                f"{item['code']:<8} "
                f"{item['name']:<28} "
                f"{item['latest_date'].strftime('%Y-%m-%d'):<12} "
                f"{nav_f}  "
                f"{dod:>8}  {wow:>8}  {mom:>8}  {qoq:>8}  "
                f"{hoh:>8}  {yoy:>8}  {ytd:>8}"
            )
    print(sep)

    # ====== HTML 推送 ======
    now_str = datetime.now().strftime('%Y%m%d')
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')

    style = """
    <meta name='viewport' content='width=device-width,initial-scale=1,maximum-scale=1'>
    <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    body { font-family:-apple-system; background:#f5f5f5; padding:12px 8px 24px; -webkit-text-size-adjust:100%; }
    .report-title { font-size:20px; font-weight:800; color:#1a1a1a; text-align:center; padding:10px 0 4px; }
    .report-date { font-size:12px; color:#999; text-align:center; margin-bottom:12px; }
    .platform-title { font-size:14px; font-weight:700; color:#555; margin:14px 0 6px 4px; padding-left:4px; border-left:3px solid #4a90d9; }
    .fund-card { background:white; border-radius:14px; padding:14px; margin:8px 0; box-shadow:0 2px 8px rgba(0,0,0,0.06); }
    .fund-card .header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px; }
    .fund-card .name { font-size:15px; font-weight:700; color:#1a1a1a; flex:1; line-height:1.3; }
    .fund-card .nav-info { text-align:right; white-space:nowrap; margin-left:8px; }
    .fund-card .nav-val { font-size:18px; font-weight:700; color:#333; }
    .fund-card .nav-dod { font-size:14px; font-weight:700; margin-top:4px; }
    .fund-card .grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px 4px; }
    .fund-card .grid .cell { text-align:center; padding:4px 2px; background:#f8f9fa; border-radius:8px; line-height:1.5; }
    .fund-card .grid .label { color:#888; font-size:10px; }
    .fund-card .grid .rank { color:#aaa; font-size:10px; }
    .fund-card .grid .rank-num { color:#555; }
    .value { font-size:15px; font-weight:700; white-space:nowrap; }
    .value.pos { color:#e74c3c; }
    .value.neg { color:#27ae60; }
    .footer { text-align:center; color:#bbb; font-size:12px; margin-top:16px; padding:8px; }
    </style>
    """

    content = f"<html><head><meta charset='utf-8'>{style}</head><body>"
    content += f"<div class='report-title'>基金日报</div>"
    content += f"<div class='report-date'>{ts}</div>"

    for platform, items in groups.items():
        content += f"<div class='platform-title'>{platform}</div>"
        for item in items:
            nav_str = f"{item['nav']:.4f}" if item['nav'] is not None else '-'

            metrics = [
                ('WoW', item['wow'], '近1周'),
                ('MoM', item['mom'], '近1月'),
                ('QoQ', item['qoq'], '近3月'),
                ('HoH', item['hoh'], '近6月'),
                ('YoY', item['yoy'], '近1年'),
                ('YTD', item['ytd'], '今年来'),
            ]

            metric_html = ''
            for label, v, rank_key in metrics:
                s, cls = val_str(v)
                r = item['ranks'].get(rank_key)
                rank_part = f"<div class='rank'>(<span class='rank-num'>{r}</span>/{item['rank_total']})</div>" if r else ''
                metric_html += f"<div class='cell'><span class='label'>{label}</span><br><span class='value {cls}'>{s}</span>{rank_part}</div>"

            dod_str, dod_cls = val_str(item['dod'])

            content += f"""<div class="fund-card">
            <div class="header">
            <div class="name">{item['name']}<br><span style="font-size:12px;color:#999;font-weight:400;">{item['code']} · {item['ftype']}</span></div>
            <div class="nav-info"><div class="nav-val">{nav_str}</div><div class="nav-dod value {dod_cls}">{dod_str}</div></div>
            </div>
            <div class="grid">{metric_html}</div></div>"""

    content += f"<div class='footer'>生成于 {ts}</div>"
    content += "</body></html>"

    ALERT_TITLE = f"基金日报 {now_str}"
    if os.environ.get('GITHUB_ACTIONS'):
        ok = send_pushplus(PUSHPLUS_TOKEN, ALERT_TITLE, content)
        print(f"\nPushPlus 推送{'成功' if ok else '失败'}")
    else:
        print("\n本地运行，跳过推送")

    # Save local preview
    with open('preview.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("已保存 preview.html")


if __name__ == '__main__':
    main()
