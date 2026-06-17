#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""002049 紫光国微 全维度技术分析"""
import urllib.request, json, math
from datetime import datetime

code = '002049'; name = '紫光国微'
RED = '\033[38;2;243;139;168m'; GREEN = '\033[38;2;166;227;161m'
YELLOW = '\033[93m'; CYAN = '\033[96m'; BOLD = '\033[1m'; RST = '\033[0m'

# ═══ 1. 实时行情 ═══
url = f'https://qt.gtimg.cn/q=sz{code}'
resp = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=10)
vals = resp.read().decode('gbk').split('"')[1].split('~')
price = float(vals[3]); open_p = float(vals[5])
high = float(vals[33]); low = float(vals[34])
change_pct = float(vals[32]); pe_ttm = float(vals[39])
mcap = float(vals[44]); turnover = float(vals[38])
vol_ratio = float(vals[49]); amount = float(vals[37])
pb = float(vals[46]); limit_up = float(vals[47]); limit_down = float(vals[48])

# ═══ 2. K线 ═══
url2 = f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sz{code}&scale=240&ma=no&datalen=120'
resp2 = urllib.request.urlopen(urllib.request.Request(url2, headers={'User-Agent':'Mozilla/5.0'}), timeout=15)
kraw = json.loads(resp2.read().decode('utf-8'))
closes = [float(k['close']) for k in kraw]; opens = [float(k['open']) for k in kraw]
highs = [float(k['high']) for k in kraw]; lows = [float(k['low']) for k in kraw]
volumes = [float(k['volume']) for k in kraw]; n = len(closes)

# ═══ 3-12: 所有计算 ═══
ma5 = sum(closes[-5:])/5; ma10 = sum(closes[-10:])/10
ma20 = sum(closes[-20:])/20; ma60 = sum(closes[-60:])/60 if n>=60 else sum(closes)/n
ma5_slope = (ma5 - sum(closes[-6:-1])/5)/(sum(closes[-6:-1])/5)*100 if n>=6 else 0

vol5 = sum(volumes[-5:])/5; vol20 = sum(volumes[-20:])/20
vol_520 = vol5/vol20 if vol20>0 else 1

high20 = max(highs[-20:]); low20 = min(lows[-20:])
high60 = max(highs[-60:]); low60 = min(lows[-60:])
pos20 = (price-low20)/(high20-low20)*100 if high20!=low20 else 50
pos60 = (price-low60)/(high60-low60)*100 if high60!=low60 else 50

e12=[closes[0]]; e26=[closes[0]]
for i in range(1,n):
    e12.append(closes[i]*2/13+e12[-1]*11/13)
    e26.append(closes[i]*2/27+e26[-1]*25/27)
dif_list=[e12[i]-e26[i] for i in range(n)]
dea_list=[dif_list[0]]
for i in range(1,n): dea_list.append(dif_list[i]*2/10+dea_list[-1]*8/10)
macd_bar=[(dif_list[i]-dea_list[i])*2 for i in range(n)]
dif=dif_list[-1]; dea=dea_list[-1]; bar=macd_bar[-1]
macd_signal='中性'
for i in range(-5,0):
    if dif_list[i-1]<=dea_list[i-1] and dif_list[i]>dea_list[i]:
        macd_signal=f'{RED}金叉{RST}'; break
    elif dif_list[i-1]>=dea_list[i-1] and dif_list[i]<dea_list[i]:
        macd_signal=f'{GREEN}死叉{RST}'; break

gains=[max(closes[i]-closes[i-1],0) for i in range(n-14,n)]
losses=[max(closes[i-1]-closes[i],0) for i in range(n-14,n)]
avg_g=sum(gains)/14; avg_l=sum(losses)/14
rsi=100-100/(1+avg_g/avg_l) if avg_l>0 else 100

l9=min(lows[-9:]); h9=max(highs[-9:])
rsv=(closes[-1]-l9)/(h9-l9)*100 if h9!=l9 else 50
k_val=rsv/3+50*2/3; d_val=k_val/3+50*2/3; j_val=3*k_val-2*d_val

bb_mid=ma20; bb_std=math.sqrt(sum((c-bb_mid)**2 for c in closes[-20:])/20)
bb_up=bb_mid+2*bb_std; bb_low=bb_mid-2*bb_std
bb_width=(bb_up-bb_low)/bb_mid*100
bb_pos=(price-bb_low)/(bb_up-bb_low)*100 if bb_up!=bb_low else 50

tr_list=[]
for i in range(n-14,n):
    tr_list.append(max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])))
atr14=sum(tr_list)/14; atr_pct=atr14/price*100

supports=[]; resistances=[]
for lb,lb_name in [(10,'10日'),(20,'20日'),(60,'60日')]:
    idx=max(0,n-lb); ll=min(lows[idx:]); hh=max(highs[idx:])
    supports.append((ll,f'{lb_name}低点')); resistances.append((hh,f'{lb_name}高点'))
for mn,mv in [('MA20',ma20),('MA60',ma60)]:
    if mv<price: supports.append((mv,mn))
    else: resistances.append((mv,mn))
supports.sort(key=lambda x:-x[0]); resistances.sort(key=lambda x:x[0])

chg5=(closes[-1]/closes[-6]-1)*100 if n>=6 else 0
chg10=(closes[-1]/closes[-11]-1)*100 if n>=11 else 0
chg20=(closes[-1]/closes[-21]-1)*100 if n>=21 else 0
chg60=(closes[-1]/closes[-61]-1)*100 if n>=61 else 0

# ═══ 13. 综合评分 ═══
score=50; signals_bull=[]; signals_bear=[]
if ma5>ma10>ma20>ma60: score+=20; signals_bull.append('完全多头排列')
elif ma5>ma10>ma20: score+=12; signals_bull.append('短期多头')
elif price<ma60: score-=15; signals_bear.append('跌破MA60')
if price>ma20: score+=5; signals_bull.append('站上MA20')
if price>ma60: score+=8; signals_bull.append('站上MA60')
if price<ma5: score-=5; signals_bear.append('跌破MA5')
if dif>dea and dif>0: score+=8; signals_bull.append('MACD多头')
elif dif>dea: score+=3
else: score-=5; signals_bear.append('MACD空头')
if 40<=rsi<=60: score+=3
elif 30<=rsi<40: score+=5; signals_bull.append('RSI偏低')
elif rsi<30: score+=8; signals_bull.append('RSI超卖')
elif rsi>70: score-=8; signals_bear.append('RSI超买')
if vol_520>1.5: score+=5; signals_bull.append('放量')
if vol_520<0.7: score-=3; signals_bear.append('缩量')
if pos20<30: score+=5; signals_bull.append('20日低位')
if pos60<35: score+=3; signals_bull.append('60日偏低')
if chg5>10: score-=10; signals_bear.append(f'5日涨{chg5:.0f}%过急')
if chg5<-10: score+=5; signals_bull.append('超跌反弹')
score=max(0,min(100,score))

# ═══ 14. 止损止盈 ═══
nearest = max(s[0] for s in supports) if supports else price*0.9
stop_support=nearest*0.97; stop_atr=price-2*atr14; stop_hard=price*0.95
stop_loss=max(stop_support,stop_atr,stop_hard)
stop_pct=(price-stop_loss)/price*100
take_profit=price+(price-stop_loss)*2; tp_pct=(take_profit-price)/price*100

# ═══ 15. 输出 ═══
sep70 = '=' * 70
print(sep70)
print(f'{BOLD}  📊 {name}({code}) 全维度操作分析{RST}')
print(f'{BOLD}  ⏰ {datetime.now().strftime("%Y-%m-%d %H:%M")} 盘中{RST}')
print(sep70)

pct_c = RED if change_pct >= 0 else GREEN
print(f'\n{BOLD}  💹 实时行情{RST}')
print(f'  现价: {BOLD}{price:.2f}{RST} 元  |  涨跌: {pct_c}{change_pct:+.2f}%{RST}  |  PE: {pe_ttm:.0f}x  |  PB: {pb:.2f}')
print(f'  市值: {mcap:.0f}亿  |  换手: {turnover:.2f}%  |  量比: {vol_ratio:.2f}  |  成交: {amount/10000:.1f}亿')
print(f'  涨停: {RED}{limit_up:.2f}{RST}  |  跌停: {GREEN}{limit_down:.2f}{RST}')

print(f'\n{BOLD}  📐 均线系统{RST}')
print(f'  MA5={ma5:.2f}  MA10={ma10:.2f}  MA20={ma20:.2f}  MA60={ma60:.2f}')
ml = [('MA5',ma5,price>ma5),('MA10',ma10,price>ma10),('MA20',ma20,price>ma20),('MA60',ma60,price>ma60)]
ma_str = ' > '.join([f'{n}={v:.2f}' for n,v,_ in ml])
print('  排列: ' + ma_str)
all_above = all(x for _,_,x in ml)
all_bull = ma5>ma10>ma20>ma60
status = f'{RED}多头排列{RST}' if all_bull else (f'{RED}多排{RST}' if ma5>ma10>ma20 else f'{YELLOW}震荡{RST}' if all_above else f'{GREEN}偏弱{RST}')
print(f'  状态: {status}  |  斜率: {ma5_slope:+.1f}%')

print(f'\n{BOLD}  📐 技术指标{RST}')
print(f'  MACD: DIF={dif:.3f}  DEA={dea:.3f}  柱={bar:+.3f}  {macd_signal}')
print(f'  RSI(14): {rsi:.1f}  |  KDJ: K={k_val:.1f} D={d_val:.1f} J={j_val:.1f}')
print(f'  布林: 上={bb_up:.2f} 中={bb_mid:.2f} 下={bb_low:.2f}  带宽={bb_width:.1f}%  位置={bb_pos:.0f}%')
print(f'  ATR: {atr14:.2f}({atr_pct:.1f}%)  |  20日区间位置: {pos20:.0f}%')

print(f'\n{BOLD}  📊 量价{RST}')
print(f'  5日均量: {vol5/1e4:.0f}万手  20日均量: {vol20/1e4:.0f}万手  比值: {vol_520:.2f}x')
print(f'  近5日: {RED if chg5>0 else GREEN}{chg5:+.1f}%{RST}  近10日: {RED if chg10>0 else GREEN}{chg10:+.1f}%{RST}  近20日: {RED if chg20>0 else GREEN}{chg20:+.1f}%{RST}  近60日: {RED if chg60>0 else GREEN}{chg60:+.1f}%{RST}')

print(f'\n{BOLD}  📍 关键价位{RST}')
sep_s = ' | '
print('  支撑: ' + sep_s.join([f'{s:.2f}({n})' for s,n in supports[:3]]))
print('  阻力: ' + sep_s.join([f'{r:.2f}({n})' for r,n in resistances[:3]]))

print(f'\n{BOLD}  ⭐ 综合评分: {score}/100{RST}')
if signals_bull: print(f'  {RED}看多信号:{sep_s.join(signals_bull)}{RST}')
if signals_bear: print(f'  {GREEN}看空信号:{sep_s.join(signals_bear)}{RST}')

print(f'\n{BOLD}  💰 风险收益计划{RST}')
print(f'  入场: {price:.2f}元  |  止损: {RED}{stop_loss:.2f}{RST}({GREEN}-{stop_pct:.1f}%{RST})  |  止盈: {GREEN}{take_profit:.2f}{RST}({RED}+{tp_pct:.1f}%{RST})')
print(f'  止损来源: 支撑{stop_support:.2f} | ATR{stop_atr:.2f} | 硬止损{stop_hard:.2f}')
print(f'  仓位: ≤20%  |  盈亏比 2:1')

print('\n' + BOLD + sep70 + RST)
if score >= 65:
    print(f'{BOLD}  🎯 操作建议: {RED}可买入{RST} (评分{score})')
    print(f'  理由: 综合技术面偏多, MA20({ma20:.2f})附近分批建仓')
elif score >= 50:
    print(f'{BOLD}  🎯 操作建议: {YELLOW}观望等待{RST} (评分{score})')
elif score >= 40:
    print(f'{BOLD}  🎯 操作建议: {YELLOW}暂不建议{RST} (评分{score})')
else:
    print(f'{BOLD}  🎯 操作建议: {GREEN}不建议买入{RST} (评分{score})')
print(sep70)
print(f'  ⚠️ A股T+1  |  PE={pe_ttm:.0f}x 芯片龙头  |  数据: 腾讯+新浪')
