#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A股实时选股 — 2026-06-17 盘中"""
import urllib.request, json

codes = [
    '600519','000858','300750','601318','000333','600036','601398',
    '601288','601939','601988','600900','002594','601857','600276',
    '603259','002475','600809','000651','002415','300059','600030',
    '688017','300308','300476','002463','603501','688981','300274',
    '002230','603160','002049','300782','688536','300604','002371',
    '600941','601728','688256','300394','603986','002916','600150',
    '002241','300502','688608','603893','300433','002384','300735',
    '600584','603236','000977','300474','600536','002439','300496',
    '688111','600570','300124','002920','002938','300033','603444',
    '600031','601899','002142','600048','000002','601668','600585',
    '000725','002304','000568','600887','601012','002027','300450',
]
codes = list(dict.fromkeys(codes))
print(f'股票池: {len(codes)} 只')
print('正在拉取行情...', end=' ', flush=True)

prefixed = []
for c in codes:
    if c.startswith(('6','9')): prefixed.append(f'sh{c}')
    elif c.startswith('8'): prefixed.append(f'bj{c}')
    else: prefixed.append(f'sz{c}')

url = 'https://qt.gtimg.cn/q=' + ','.join(prefixed)
req = urllib.request.Request(url)
req.add_header('User-Agent', 'Mozilla/5.0')
resp = urllib.request.urlopen(req, timeout=20)
data = resp.read().decode('gbk', errors='replace')

results = []
for line in data.strip().split(';'):
    if '=' not in line or '"' not in line: continue
    vals = line.split('"')[1].split('~')
    if len(vals) < 53: continue
    code = line.split('=')[0].split('_')[-1][2:]
    try:
        results.append({
            'code': code, 'name': vals[1],
            'price': float(vals[3]) if vals[3] else 0,
            'change_pct': float(vals[32]) if vals[32] else 0,
            'pe_ttm': float(vals[39]) if vals[39] else 999,
            'mcap_yi': float(vals[44]) if vals[44] else 0,
            'turnover': float(vals[38]) if vals[38] else 0,
            'vol_ratio': float(vals[49]) if vals[49] else 0,
            'high': float(vals[33]) if vals[33] else 0,
            'low': float(vals[34]) if vals[34] else 0,
            'amount_wan': float(vals[37]) if vals[37] else 0,
            'pb': float(vals[46]) if vals[46] else 0,
            'open': float(vals[5]) if vals[5] else 0,
        })
    except: pass
print(f'{len(results)} 只有效行情')

# 粗筛
coarse = []
for r in results:
    if 'ST' in r['name']: continue
    if r['pe_ttm'] <= 0 or r['pe_ttm'] > 300: continue
    if r['mcap_yi'] < 30 or r['mcap_yi'] > 2000: continue
    if r['turnover'] < 0.8: continue
    if r['vol_ratio'] < 0.7: continue
    coarse.append(r)
print(f'粗筛后: {len(coarse)} 只')

# 精筛评分
for r in coarse:
    score = 0; reasons = []
    pct = r['change_pct']; vol = r['vol_ratio']; to = r['turnover']
    pe = r['pe_ttm']; amt = r['amount_wan']

    if pct > 3: score += 25; reasons.append(f'强涨{pct:+.1f}%')
    elif pct > 0: score += 18; reasons.append(f'涨{pct:+.1f}%')
    elif pct > -1: score += 10
    elif pct > -3: score += 3

    if vol >= 2.5: score += 20; reasons.append('大幅放量')
    elif vol >= 1.5: score += 13; reasons.append('放量')
    elif vol >= 1.0: score += 8

    if to >= 8: score += 15; reasons.append('高度活跃')
    elif to >= 5: score += 10
    elif to >= 2: score += 6

    if pe <= 30: score += 12; reasons.append('低估值')
    elif pe <= 50: score += 8
    elif pe <= 80: score += 5

    if amt >= 200000: score += 10; reasons.append('天量成交')
    elif amt >= 50000: score += 7; reasons.append('活跃')
    elif amt >= 20000: score += 4

    if r['price'] > 0:
        amp = (r['high']-r['low'])/r['price']*100
        if amp > 0 and pct > 0:
            strength = pct/amp*100
            if strength > 60: score += 10; reasons.append('强势上攻')
            elif strength > 40: score += 5

    if r['price'] > r['open']: score += 8; reasons.append('阳线')

    r['score'] = score; r['reasons'] = ' | '.join(reasons)

coarse.sort(key=lambda x: x['score'], reverse=True)
top = coarse[:20]

RED = '\033[38;2;243;139;168m'; GREEN = '\033[38;2;166;227;161m'
YELLOW = '\033[93m'; BOLD = '\033[1m'; RST = '\033[0m'

print(f'\n{BOLD}{"="*80}{RST}')
print(f'{BOLD}  📊 A股买入候选 — 2026-06-17 盘中实时 {RST}')
print(f'{"="*80}')
print(f'  {"代码":<8s} {"名称":<8s} {"现价":>7s} {"涨跌":>8s} {"PE":>5s} {"市值":>7s} {"换手":>6s} {"量比":>5s} {"评分":>4s}  信号')
print(f'  {"-"*78}')

for r in top:
    up = r['change_pct'] > 0
    color = RED if up else GREEN
    pct_str = f'{color}{r["change_pct"]:>+6.1f}%{RST}'
    grade = '🔥' if r['score']>=70 else ('⭐' if r['score']>=55 else ('○' if r['score']>=40 else '  '))
    print(f'  {r["code"]:<8s} {r["name"]:<8s} {r["price"]:>7.2f} {pct_str} {r["pe_ttm"]:>5.0f} {r["mcap_yi"]:>6.0f}亿 {r["turnover"]:>5.1f}% {r["vol_ratio"]:>5.2f} {r["score"]:>4d}  {grade}')

print(f'  {"="*80}')
print(f'  🔥=强烈推荐(>=70) ⭐=推荐(>=55) ○=关注(>=40)')
print(f'  红涨 / 绿跌 | PE=TTM | 换手=换手率%')
print()

# TOP5均线分析
print(f'{BOLD}📈 TOP5 均线多头排列分析:{RST}')
top5 = top[:5]
for r in top5:
    code = r['code']
    try:
        url2 = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,60,qfq'
        req2 = urllib.request.Request(url2)
        req2.add_header('User-Agent', 'Mozilla/5.0')
        resp2 = urllib.request.urlopen(req2, timeout=10)
        kdata = json.loads(resp2.read().decode('utf-8'))
        days = kdata.get('data',{}).get(code,{}).get('day',[]) or kdata.get('data',{}).get(code,{}).get('qfqday',[])
        if not days:
            print(f'  {code} {r["name"]}: K线数据获取失败')
            continue
        closes = [float(d[2]) for d in days[-60:]]
        if len(closes) < 20:
            print(f'  {code} {r["name"]}: 数据不足')
            continue
        ma5 = sum(closes[-5:])/5
        ma10 = sum(closes[-10:])/10
        ma20 = sum(closes[-20:])/20
        price = r['price']
        vol_last5 = sum(float(d[5]) for d in days[-5:])/5
        vol_all20 = sum(float(d[5]) for d in days[-20:])/20
        vol_ratio_5d = vol_last5/vol_all20 if vol_all20>0 else 1

        ma_status = []
        if price > ma5: ma_status.append('站上MA5')
        if price > ma10: ma_status.append('MA10')
        if price > ma20: ma_status.append('MA20')
        if ma5 > ma10 > ma20: ma_status.append('多头排列')
        elif ma5 > ma10: ma_status.append('短期多头')

        status_color = RED if '多头排列' in ' '.join(ma_status) else YELLOW
        print(f'  {code} {r["name"]:<6s}  {price:.2f} | MA5={ma5:.2f} MA10={ma10:.2f} MA20={ma20:.2f}')
        sep = ' | '
        print(f'    {status_color}{sep.join(ma_status)}{RST} | 5日放量={vol_ratio_5d:.1f}x | 评分={r["score"]}')
    except Exception as e:
        print(f'  {code} {r["name"]}: K线分析失败 - {e}')

print()
print(f'{BOLD}📋 建议操作:{RST}')
print('  ⚠️ 以上为盘中实时数据筛选，仅供参考')
print('  ⚠️ A股T+1规则：今日买入，明日方可卖出')
print('  ⚠️ 建议分散持仓 ≤5只，单票仓位 ≤20%')
print('  ⚠️ 止损设在支撑位下方3%或买入价-5%')
