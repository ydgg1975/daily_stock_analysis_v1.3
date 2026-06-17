#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A股交易日历"""
from datetime import datetime, time, date, timedelta
from typing import Optional

HOLIDAYS_2026 = {
    '2026-01-01','2026-01-02','2026-02-16','2026-02-17','2026-02-18','2026-02-19','2026-02-20',
    '2026-04-06','2026-05-01','2026-05-04','2026-05-05','2026-06-19',
    '2026-09-25','2026-10-01','2026-10-02','2026-10-05','2026-10-06','2026-10-07',
}
MORNING_START = time(9,30); MORNING_END = time(11,30)
AFTERNOON_START = time(13,0); AFTERNOON_END = time(15,0)

def is_trading_day(d=None):
    d = d or date.today()
    if d.weekday() >= 5: return False
    return d.strftime('%Y-%m-%d') not in HOLIDAYS_2026

def get_trading_session(now=None):
    now = now or datetime.now()
    if not is_trading_day(now.date()): return 'closed'
    t = now.time()
    if t < time(9,15): return 'pre_auction'
    if t <= time(9,25): return 'auction'
    if t < MORNING_START: return 'pre_market'
    if t <= MORNING_END: return 'morning'
    if t < AFTERNOON_START: return 'lunch_break'
    if t <= AFTERNOON_END: return 'afternoon'
    return 'closed'

def is_market_open(now=None):
    return get_trading_session(now) in ('morning','afternoon')

if __name__ == '__main__':
    print(f'交易日: {is_trading_day()}, 时段: {get_trading_session()}')
