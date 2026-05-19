import { describe, expect, it } from 'vitest';
import { markdownToPlainText } from '../markdown';

/**
 * Stock report specific tests for markdownToPlainText
 * Tests real-world stock analysis report scenarios
 */
describe('markdownToPlainText - Stock Report Scenarios', () => {
  it('handles typical Chinese stock report with tables and indicators', () => {
    const stockReport = `# guizhoumaotai (600519) fenxibaogao

## jishufenxi

| zhibiao | dangqianzhi | xinhao |
|------|--------|------|
| MA5 | 1680.50 | 🟢 |
| MA10 | 1675.30 | 🟢 |
| MA20 | 1665.80 | 🟢 |

**MACD**: jinchaxinhao，mairucankao
**RSI**: 56.8，chuyuzhongxingquyu

## jibenmianfenxi

- **shiyinglv**: 28.5
- **shijinglv**: 8.2
- **yingshouzengzhang**: +15.3% YoY

> fengxiantishi：duanqibodongjiada，jianyikongzhicangwei

## caozuojianyi

\`\`\`python
# tuijianmairuqujian
entry_zone = [1650, 1680]
stop_loss = 1620
target = 1750
\`\`\`

[chakanxiangxishuju](https://example.com/stock/600519)`;

    const result = markdownToPlainText(stockReport);

    // Verify key content is preserved
    expect(result).toContain('guizhoumaotai');
    expect(result).toContain('600519');
    expect(result).toContain('jishufenxi');
    expect(result).toContain('MACD');
    expect(result).toContain('jinchaxinhao');
    expect(result).toContain('shiyinglv');
    expect(result).toContain('fengxiantishi');
    expect(result).toContain('entry_zone');
    expect(result).toContain('chakanxiangxishuju');

    // Verify markdown symbols are removed
    expect(result).not.toMatch(/^#{1,6}\s+/m);
    expect(result).not.toMatch(/\*\*[^*]+\*\*/);
    // Note: remove-markdown preserves table structure with pipe characters
    // This is a known limitation - tables remain pipe-separated
  });

  it('handles Hong Kong stock report with English and Chinese mix', () => {
    const hkReport = `# Tencent (00700.HK) Technical Analysis

## Key Indicators

* **Current Price**: HKD 368.20
* **Change**: +2.5% 📈
* **Volume**: 18.2M

## Support & Resistance

1. **Resistance 1**: HKD 375.00
2. **Resistance 2**: HKD 380.00
3. **Support 1**: HKD 365.00

> jianyizaihuidiaozhi 365-368 qujianguanzhu

\`\`\`
MA5 > MA10 > MA20 (duotoupailie)
RSI(14) = 58.3 (zhongxingpianqiang)
\`\`\`

[Click for more details](https://finance.qq.com/q/go.php/vInvestConsult/stock/00700)`;

    const result = markdownToPlainText(hkReport);

    expect(result).toContain('Tencent');
    expect(result).toContain('00700.HK');
    expect(result).toContain('368.20');
    expect(result).toContain('Resistance 1');
    expect(result).toContain('Support 1');
    expect(result).toContain('jianyizaihuidiao');
    expect(result).toContain('MA5 > MA10');
    expect(result).toContain('Click for more details');
  });

  it('handles US stock report with financial data', () => {
    const usReport = `# Apple Inc. (AAPL) Analysis Report

## Financial Metrics

| Metric | Value | Change |
|--------|-------|--------|
| Price | $178.35 | +1.2% |
| Market Cap | $2.8T | - |
| P/E Ratio | 28.5 | - |
| EPS | $6.16 | +8.3% |

## Technical Indicators

- **MA50**: $175.20 (Above)
- **MA200**: $168.80 (Above)
- **RSI**: 62.5 (Slightly Overbought)
- **MACD**: Bullish crossover

## Recommendation

***Strong Buy*** with target price of **$195.00**

> Risk: Trade tensions may impact supply chain

\`\`\`javascript
const entryPrice = 178.35;
const stopLoss = 172.00;
const targetPrice = 195.00;
const riskReward = (targetPrice - entryPrice) / (entryPrice - stopLoss);
// Risk/Reward ratio: 2.1:1
\`\`\`

![AAPL Chart](https://example.com/charts/aapl.png)`;

    const result = markdownToPlainText(usReport);

    expect(result).toContain('Apple Inc.');
    expect(result).toContain('AAPL');
    expect(result).toContain('178.35');
    expect(result).toContain('2.8T');
    expect(result).toContain('Strong Buy');
    expect(result).toContain('195.00');
    expect(result).toContain('Risk/Reward ratio');
  });

  it('handles market review report with multiple stocks', () => {
    const marketReview = `# Agushichangfupan

## zhishubiaoxian

| zhishu | shoupan | zhangdiefu | chengjiaoe |
|------|------|--------|--------|
| shangzhengzhishu | 3050.32 | +0.85% | 4285yi |
| shenzhengchengzhi | 9850.45 | +1.12% | 5250yi |
| chuangyebanzhi | 1950.28 | +1.45% | 2180yi |

## redianbankuai

1. **rengongzhineng** 🤖
   - yuanyin：damoxingjishutupo
   - longtou：kedaxunfei、hanwuji

2. **xinnengyuanqiche** 🚗
   - yuanyin：xiaoliangshujuchaoyuqi
   - longtou：biyadi、lixiangqiche

3. **bandaoti** 💾
   - yuanyin：guochantidaijiasu
   - longtou：zhongxinguoji、beifanghuachuang

## zijinliuxiang

- **beixiangzijin**: +85.5yi
- **rongzirongquan**: +32.8yi
- **zhulizijin**: jingliuru 156.8yi

## houshizhanwang

> yuqimingrizhendangqujian：3040-3065

**celve**：guanzhukejizhuxian，kongzhicangwei`;

    const result = markdownToPlainText(marketReview);

    expect(result).toContain('Agushichangfupan');
    expect(result).toContain('shangzhengzhishu');
    expect(result).toContain('3050.32');
    expect(result).toContain('rengongzhineng');
    expect(result).toContain('kedaxunfei');
    expect(result).toContain('beixiangzijin');
    expect(result).toContain('85.5yi');
    expect(result).toContain('3040-3065');
  });

  it('handles report with special characters and formulas', () => {
    const report = `# jishuzhibiaojisuan

## MACD jisuan

\`\`\`python
# MACD = EMA(12) - EMA(26)
# Signal = EMA(MACD, 9)
# Histogram = MACD - Signal

def calculate_macd(prices, fast=12, slow=26, signal=9):
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal).mean()
    return macd, signal_line
\`\`\`

## RSI gongshi

$$RSI = 100 - \frac{100}{1 + RS}$$

qizhong：
- RS = pingjunzhangfu / pingjundiefu
- zhouqi：moren 14 tian

## bulindai

- **zhonggui** = MA(20)
- **shanggui** = MA(20) + 2 × STD(20)
- **xiagui** = MA(20) - 2 × STD(20)

> dangqiangujiazaishangguifujin，zhuyihuidiaofengxian`;

    const result = markdownToPlainText(report);

    expect(result).toContain('MACD jisuan');
    expect(result).toContain('EMA(12) - EMA(26)');
    expect(result).toContain('RSI');
    expect(result).toContain('bulindai');
    expect(result).toContain('MA(20)');
    expect(result).toContain('zhuyihuidiaofengxian');
  });

  it('handles report with code snippets in multiple languages', () => {
    const report = `# celvehuicedaima

## Python celve

\`\`\`python
import pandas as pd
import numpy as np

def moving_average_strategy(data, short=5, long=20):
    signals = pd.DataFrame(index=data.index)
    signals['signal'] = 0

    signals['short_ma'] = data['close'].rolling(window=short).mean()
    signals['long_ma'] = data['close'].rolling(window=long).mean()

    signals.loc[signals['short_ma'] > signals['long_ma'], 'signal'] = 1
    signals.loc[signals['short_ma'] < signals['long_ma'], 'signal'] = -1

    return signals
\`\`\`

yishangdaimakezhijieyongyucelvehuice。`;

    const result = markdownToPlainText(report);

    // Verify key content is preserved
    expect(result).toContain('celvehuicedaima');
    expect(result).toContain('Python celve');
    expect(result).toContain('yishangdaimakezhijieyongyucelvehuice');

    // Verify code content is preserved
    expect(result).toContain('import pandas');
    expect(result).toContain('moving_average_strategy');
  });

  it('handles edge case: very long stock code list', () => {
    const stockList = `# gupiaochiliebiao

## hushen300chengfengu（bufen）

| daima | mingcheng | xianjia | zhangdiefu |
|------|------|------|--------|
| 600519 | guizhoumaotai | 1680.50 | +0.85% |
| 000858 | wuliangye | 125.30 | +1.20% |
| 600036 | zhaoshangyinhang | 32.50 | -0.25% |
| 000001 | pinganyinhang | 11.85 | +0.42% |
| 601318 | zhongguopingan | 45.20 | +0.15% |
| 000333 | meidejituan | 58.80 | +1.80% |
| 600276 | hengruiyiyao | 42.50 | +2.10% |
| 300750 | ningdeshidai | 185.30 | +3.20% |
| 688981 | zhongxinguoji | 52.80 | +4.50% |
| 601012 | longjilvneng | 25.60 | -1.20% |

## shaixuantiaojian

- **shizhi**: > 500yi
- **PE**: 10-50
- **ROE**: > 15%
- **fuzhailv**: < 60%`;

    const result = markdownToPlainText(stockList);

    // Verify all stock codes are preserved
    expect(result).toContain('600519');
    expect(result).toContain('000858');
    expect(result).toContain('601012');
    expect(result).toContain('guizhoumaotai');
    expect(result).toContain('ningdeshidai');
    expect(result).toContain('shaixuantiaojian');
    expect(result).toContain('ROE');
  });

  it('handles mixed Chinese and English punctuation correctly', () => {
    const text = `# baogaozhaiyao

**zhuyaoguandian**：
1. duanqikanzhang，mubiaojia $195.00
2. zhichengwei：$168.50-172.00
3. yaliwei：$180.50-185.00

"Risk: Trade war impact"

> fengxiantishi：zhongmeimaoyimocakenengyingxiangchukou

*guanzhudian*：AI chip business growth`;

    const result = markdownToPlainText(text);

    expect(result).toContain('zhuyaoguandian');
    expect(result).toContain('duanqikanzhang');
    expect(result).toContain('195.00');
    expect(result).toContain('Risk: Trade war impact');
    expect(result).toContain('fengxiantishi');
    expect(result).toContain('guanzhudian');
    expect(result).toContain('AI chip business');
  });

  it('preserves numerical data and percentages accurately', () => {
    const report = `# shujubaogao

## guanjianzhibiao

- yingshou: 1,234.56yi
- jinglirun: +23.45%
- shizhanlv: 15.67%
- ROE: 18.9%
- fuzhailv: 45.2%

## jiagequjian

| riqi | kaipan | zuigao | zuidi | shoupan |
|------|------|------|------|------|
| 2024-01-15 | 1680.50 | 1695.30 | 1675.20 | 1688.80 |
| 2024-01-16 | 1688.80 | 1702.50 | 1685.30 | 1698.20 |

zhangdiefu: +1.23% (jinri)`;

    const result = markdownToPlainText(report);

    expect(result).toContain('1,234.56');
    expect(result).toContain('23.45%');
    expect(result).toContain('15.67%');
    expect(result).toContain('1680.50');
    expect(result).toContain('1695.30');
    expect(result).toContain('1.23%');
  });
});
