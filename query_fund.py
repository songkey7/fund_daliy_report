import sys
import pandas as pd
import requests
from datetime import datetime, timedelta
import akshare as ak

FUND_NAMES = {
    '012349': '天弘恒生科技ETF联接(QDII)C',
    '001156': '申万菱信新能源汽车混合',
    '016710': '华安中证新能源汽车ETF联接C',
    '018304': '华夏聚源优选三个月持有混合(FOF)A',
    '012805': '广发恒生科技ETF联接(QDII)C',
    '004744': '易方达创业板ETF联接C',
    '022429': '天弘中证A500ETF联接C',
}

def parse_fund_file(filepath):
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.read().strip().split('\n')
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split(',')
        if len(parts) < 5:
            continue
        code, buy_date, amount, stop_loss, stop_profit = parts[:5]
        records.append({
            'code': code.strip(),
            'buy_date': buy_date.strip(),
            'amount': float(amount.strip()),
            'stop_loss': float(stop_loss.strip()),
            'stop_profit': float(stop_profit.strip()),
        })
    return records


def query_fund_all(code):
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势", period="成立来")
        if df is None or df.empty:
            return None

        col_map = {}
        for c in df.columns:
            c_str = str(c).strip()
            if ('日' in c_str or '期' in c_str) and '日增长' not in c_str:
                col_map[c] = 'date'
            elif '净' in c_str and '日增长' not in c_str:
                col_map[c] = 'nav'
        if len(set(col_map.values())) < 2:
            print(f"[{code}] duplicate mapping: {col_map}", file=sys.stderr)
            return None
        df = df.rename(columns=col_map)
        if 'date' not in df.columns or 'nav' not in df.columns:
            print(f"[{code}] col rename failed, columns: {list(df.columns)}", file=sys.stderr)
            return None
        df['date'] = pd.to_datetime(df['date'])
        df['nav'] = df['nav'].astype(float)
        df = df.sort_values('date', ascending=False).reset_index(drop=True)
        return df
    except Exception as e:
        print(f"[{code}] query error: {e}", file=sys.stderr)
        return None


def calc_return(df, lookback_days):
    if df is None or df.empty:
        return None
    data = df.copy()
    data = data.sort_values('date', ascending=False).reset_index(drop=True)
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
    data = df.copy()
    data['date'] = pd.to_datetime(data['date'])
    data = data.sort_values('date', ascending=False).reset_index(drop=True)

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


def calc_buy_return(df, buy_date_str):
    if df is None or df.empty:
        return None
    data = df.copy()
    data['date'] = pd.to_datetime(data['date'])
    data = data.sort_values('date', ascending=False).reset_index(drop=True)

    latest_nav = float(data['nav'].iloc[0])
    buy_date = datetime.strptime(buy_date_str, '%Y%m%d')

    found = data[data['date'] <= buy_date]
    if found.empty:
        return None

    base_nav = float(found['nav'].iloc[0])
    if base_nav == 0:
        return None

    return round((latest_nav - base_nav) / base_nav * 100, 2)


def send_pushplus(token, title, content):
    """通过PushPlus推送消息"""
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


def main():
    records = parse_fund_file('fund.txt')

    if not records:
        print("未找到基金数据")
        return

    results = []

    for rec in records:
        code = rec['code']
        name = FUND_NAMES.get(code, code)
        df = query_fund_all(code)
        if df is None:
            continue

        item = {
            'code': code,
            'name': name,
            'latest_date': df['date'].iloc[0],
            'nav': df['nav'].iloc[0],
            'dod': calc_return(df, 1),
            'wow': calc_return(df, 5),
            'mom': calc_return(df, 22),
            'qoq': calc_return(df, 66),
            'hoh': calc_return(df, 126),
            'yoy': calc_return(df, 252),
            'ytd': calc_ytd_return(df),
            'buy': calc_buy_return(df, rec['buy_date']),
            'buy_date': rec['buy_date'],
            'amount': rec['amount'],
            'stop_loss': rec['stop_loss'],
            'stop_profit': rec['stop_profit'],
        }
        results.append(item)

    if not results:
        return

    names_width = max(len(item['name']) for item in results) + 2
    sep = "-" * (200)
    print(sep)
    print(
        f"{'代码':<10} {'名称':<{names_width}} {'日期':<12} {'净值':>10} "
        f"{'日涨跌':>8} {'周涨跌':>8} {'月涨跌':>8} {'季涨跌':>8} "
        f"{'半年':>8} {'年涨跌':>8} {'YTD':>8} {'购入回报':>8}  "
        f"{'购入日期':<10} {'购入金额':>10} {'止损':>5} {'止盈':>5}"
    )
    print(sep)

    for item in results:
        nav_f = format(item['nav'], '10.4f') if item['nav'] is not None else "    -     "
        dod = format(item['dod'], '+8.2f') + "%" if item['dod'] is not None else "       -"
        wow = format(item['wow'], '+8.2f') + "%" if item['wow'] is not None else "       -"
        mom = format(item['mom'], '+8.2f') + "%" if item['mom'] is not None else "       -"
        qoq = format(item['qoq'], '+8.2f') + "%" if item['qoq'] is not None else "       -"
        hoh = format(item['hoh'], '+8.2f') + "%" if item['hoh'] is not None else "       -"
        yoy = format(item['yoy'], '+8.2f') + "%" if item['yoy'] is not None else "       -"
        ytd = format(item['ytd'], '+8.2f') + "%" if item['ytd'] is not None else "       -"
        buy_ret = format(item['buy'], '+8.2f') + "%" if item['buy'] is not None else "       -"

        print(
            f"{item['code']:<10} "
            f"{item['name']:<{names_width}} "
            f"{item['latest_date'].strftime('%Y-%m-%d'):<12} "
            f"{nav_f}  "
            f"{dod}  "
            f"{wow}  "
            f"{mom}  "
            f"{qoq}  "
            f"{hoh}  "
            f"{yoy}  "
            f"{ytd}  "
            f"{buy_ret}  "
            f"{item['buy_date']:<10} "
            f"{item['amount']:>10.0f} "
            f"{item['stop_loss']:>+4.0f}% "
            f"{item['stop_profit']:>+4.0f}%"
        )
    print(sep)

    alerts = []
    for item in results:
        code = item['code']
        name = item['name']
        buy_ret = item['buy']
        stop_loss = item['stop_loss']
        stop_profit = item['stop_profit']

        if buy_ret is not None:
            if stop_profit != 0 and buy_ret >= stop_profit:
                alerts.append((code, name, '止盈', buy_ret, stop_profit))
            if stop_loss != 0 and buy_ret <= stop_loss:
                alerts.append((code, name, '止损', buy_ret, stop_loss))

    if alerts:
        print("\n" + "="*60)
        print("  ⚠️  触发信号")
        print("="*60)
        for a in alerts:
            code, name, atype, cur, th = a
            print(f"  {code} {name} 触发**{atype}** 信号，购入回报 {cur:+.2f}%，阈值: {th:+.2f}%")
        print("="*60)
    else:
        print("\n  ✓ 没有触发止损或止盈信号")

    print()

    # ===== 构建 HTML 样式推送 =====
    now_str = datetime.now().strftime('%Y%m%d')
    style = """
    <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI'; background:#f5f5f5; padding: 0; margin: 0; }
    .card { background: white; border-radius: 12px; padding: 16px; margin: 12px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    .card h3 { margin: 0 0 8px 0; font-size: 18px; }
    .metrics { display: flex; flex-wrap: wrap; gap: 8px; }
    .metric { background: #f0f0f0; border-radius: 8px; padding: 6px 12px; font-size: 14px; }
    .metric.positive { color: #e74c3c; font-weight: bold; }
    .metric.negative { color: #27ae60; font-weight: bold; }
    .buy_ret { font-size: 16px; font-weight: bold; margin-top: 8px; }
    .alert_signal { color: #e74c3c; font-weight: bold; }
    .profit_signal { color: #2ecc71; font-weight: bold; }
    .divider { border-bottom: 1px solid #ddd; margin: 8px 0; }
    </style>
    """
    content = f"<html><head>{style}</head><body>"
    content += f"<h2 style='text-align:center; color:#333;'>基金日报 {now_str}</h2>"

    signals = {a[0]: a[2] for a in alerts}

    for item in results:
        code = item['code']
        name = item['name']
        stop_loss = item['stop_loss']
        stop_profit = item['stop_profit']
        signal_type = signals.get(code)

        color = ''
        if signal_type == '止盈':
            color = '❌'
        elif signal_type == '止损':
            color = '⬆'

        pos_class = 'positive' if item['buy'] is not None and item['buy'] > 0 else 'negative'
        buy_ret_str = f"{item['buy']:+.2f}%" if item['buy'] is not None else "-"

        record = f"<div class='card'>"
        record += f"<h3>{color} {name} ({code})</h3>"
        record += "<div class='metrics'>"
        record += f"<span class='metric'><span style='color:#666;'>▼</span>d {item['dod']:+.2f}%</span>"
        record += f"<span class='metric'><span style='color:#666;'>Ⓦ</span>w {item['wow']:+.2f}%</span>"
        record += f"<span class='metric'><span style='color:#666;'>▼</span>m {item['mom']:+.2f}%</span>"
        record += f"<span class='metric'><span style='color:#666;'>▼</span>q {item['qoq']:+.2f}%</span>"
        record += f"<span class='metric'><span style='color:#666;'>▼</span>{item['hoh']:+.2f}%半年</span>"
        record += f"<span class='metric'><span style='color:#666;'>▼</span>{item['yoy']:+.2f}%年</span>"
        record += f"<span class='metric'><span style='color:#666;'>▼</span>{item['ytd']:+.2f}%YTD</span>"
        record += "</div>"
        record += f"<div class='buy_ret'>📊️ {buy_ret_str}</span>"
        record += f" <span class='{pos_class}'>"
        if signal_type:
            record += f"<span class='alert_signal'>⬆️ {signal_type} 信号触发</span>"
        record += "</div></div>"

        content += record

    if alerts:
        content += "<br><div class='card'>"
        content += "<h3>⚠️ 止盈/止损提醒</h3>"
        for code, name, atype, cur, th in alerts:
            content += f"<p>● {name} ({code})：{atype} {cur:+.2f}% (触发{th:+.2f}%)</p>"
        content += "</div>"

    content += "</body></html>"

    token = "afe064ab9d6f4db1b0aac211555d54e3"
    ALERT_TITLE = f"基金日报 {now_str}"

    send_pushplus(token, ALERT_TITLE, content)


if __name__ == '__main__':
    main()
