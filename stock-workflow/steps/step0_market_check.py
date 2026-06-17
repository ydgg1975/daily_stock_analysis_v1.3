#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Step 0: 市场体检 — 宏观环境+大盘指数+北向资金+板块热度"""
import urllib.request, json, logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

MAJOR_INDICES = {
    '000001': '上证指数', '399001': '深证成指', '399006': '创业板指',
    '000688': '科创50', '000300': '沪深300', '000905': '中证500',
}

def check_market_environment() -> Dict[str, Any]:
    result = {'bullish': True, 'score': 50, 'index_status': {},
              'north_flow': 0, 'industry_heat': {}, 'advice': '中性'}

    # 1. 指数行情
    try:
        prefixed = []
        for code in MAJOR_INDICES:
            pfx = 'sh' if code.startswith(('0','6','9')) else 'sz'
            prefixed.append(pfx + code)
        url = 'https://qt.gtimg.cn/q=' + ','.join(prefixed)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read().decode('gbk', errors='replace')
        idx_score = 0; cnt = 0
        for line in data.strip().split(';'):
            if '=' not in line or '"' not in line: continue
            vals = line.split('"')[1].split('~')
            if len(vals) < 53: continue
            code = line.split('=')[0].split('_')[-1][2:]
            name = MAJOR_INDICES.get(code, code)
            pct = float(vals[32]) if vals[32] else 0
            result['index_status'][code] = {'name': name, 'pct': pct}
            cnt += 1
            if pct > 0.5: idx_score += 10
            elif pct > 0: idx_score += 5
            elif pct < -2: idx_score -= 10
        if cnt > 0: result['score'] += idx_score / cnt
    except Exception as e:
        logger.warning(f'指数行情失败: {e}')

    # 2. 北向资金
    try:
        url = 'https://push2.eastmoney.com/api/qt/kamt.kline/get?fields1=f1,f2,f3,f4&fields2=f51,f52,f53,f54&klt=101&lmt=1'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        d = json.loads(resp.read().decode('utf-8'))
        klines = d.get('data', {}).get('klines', [])
        if klines:
            parts = klines[-1].split(',')
            north = float(parts[1]) if len(parts) > 1 else 0
            result['north_flow'] = north
            if north > 30: result['score'] += 10
            elif north > 0: result['score'] += 5
            elif north < -30: result['score'] -= 10
    except: pass

    # 3. 行业板块
    try:
        url = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=10&po=1&np=1&fltt=2&invt=2&fs=m:90+t:2&fields=f2,f3,f4,f12,f14,f104,f105'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        d = json.loads(resp.read().decode('utf-8'))
        for item in d.get('data', {}).get('diff', [])[:5]:
            result['industry_heat'][item.get('f14', '')] = item.get('f3', 0)
    except: pass

    s = round(result['score'], 1); result['score'] = s
    if s >= 65: result['advice'] = '偏多，可积极选股'
    elif s >= 50: result['advice'] = '中性偏多，正常操作'
    elif s >= 40: result['advice'] = '偏空，降低仓位'
    else: result['bullish'] = False; result['advice'] = '空头，暂停买入'
    return result

if __name__ == '__main__':
    r = check_market_environment()
    print(f"市场评分: {r['score']} | {r['advice']}")
    for c, v in r['index_status'].items():
        print(f"  {c} {v['name']}: {v['pct']:+.2f}%")
