import { describe, expect, it } from 'vitest';
import type { RuleBacktestRunResponse } from '../../../types/backtest';
import { normalizeDeterministicBacktestResult } from '../normalizeDeterministicBacktestResult';

function makeRun(overrides: Partial<RuleBacktestRunResponse> = {}): RuleBacktestRunResponse {
  return {
    id: 1,
    code: 'ORCL',
    strategyText: 'MA cross',
    parsedStrategy: {} as RuleBacktestRunResponse['parsedStrategy'],
    strategyHash: 'hash',
    timeframe: 'daily',
    startDate: '2026-03-01',
    endDate: '2026-03-03',
    periodStart: '2026-03-01',
    periodEnd: '2026-03-03',
    lookbackBars: 252,
    initialCapital: 100000,
    feeBps: 0,
    slippageBps: 0,
    parsedConfidence: 0.97,
    needsConfirmation: false,
    warnings: [],
    runAt: '2026-03-10T08:00:00Z',
    completedAt: '2026-03-10T08:03:00Z',
    status: 'completed',
    statusMessage: 'done',
    statusHistory: [],
    noResultReason: null,
    noResultMessage: null,
    tradeCount: 1,
    winCount: 1,
    lossCount: 0,
    totalReturnPct: 5,
    annualizedReturnPct: 8,
    benchmarkMode: 'auto',
    benchmarkCode: null,
    benchmarkReturnPct: 4,
    excessReturnVsBenchmarkPct: 1,
    buyAndHoldReturnPct: 3.5,
    excessReturnVsBuyAndHoldPct: 1.5,
    winRatePct: 100,
    avgTradeReturnPct: 5,
    maxDrawdownPct: -1.5,
    avgHoldingDays: 4,
    avgHoldingBars: 4,
    avgHoldingCalendarDays: 5,
    finalEquity: 105000,
    summary: {},
    executionAssumptions: {},
    benchmarkCurve: [],
    benchmarkSummary: {
      label: 'QQQ',
      requestedMode: 'auto',
      resolvedMode: 'etf_qqq',
      method: 'benchmark_security',
      returnPct: 4,
    },
    buyAndHoldCurve: [],
    buyAndHoldSummary: {
      label: '当前标的买入并持有',
      requestedMode: 'same_symbol_buy_and_hold',
      resolvedMode: 'same_symbol_buy_and_hold',
      method: 'same_symbol_buy_and_hold',
      returnPct: 3.5,
    },
    auditRows: [],
    dailyReturnSeries: [],
    exposureCurve: [],
    aiSummary: null,
    equityCurve: [],
    trades: [],
    ...overrides,
  };
}

describe('normalizeDeterministicBacktestResult', () => {
  it('normalizes audit rows into one ordered row model with non-empty series metadata', () => {
    const normalized = normalizeDeterministicBacktestResult(makeRun({
      auditRows: [
        {
          date: '2026-03-01',
          targetPosition: 0,
          totalPortfolioValue: 100000,
          cumulativeStrategyReturnPct: 0,
          cumulativeBenchmarkReturnPct: 0,
          cumulativeBuyAndHoldReturnPct: 0,
          dailyPnl: 0,
          dailyReturnPct: 0,
        },
        {
          date: '2026-03-02',
          targetPosition: 1,
          executedAction: 'buy',
          fillPrice: 101,
          sharesHeld: 100,
          cash: 89900,
          totalPortfolioValue: 102000,
          cumulativeStrategyReturnPct: 2,
          cumulativeBenchmarkReturnPct: 1.2,
          cumulativeBuyAndHoldReturnPct: 1.1,
          dailyPnl: 2000,
          dailyReturnPct: 2,
        },
        {
          date: '2026-03-03',
          targetPosition: 0,
          executedAction: 'sell',
          fillPrice: 105,
          sharesHeld: 0,
          cash: 105000,
          totalPortfolioValue: 105000,
          cumulativeStrategyReturnPct: 5,
          cumulativeBenchmarkReturnPct: 4,
          cumulativeBuyAndHoldReturnPct: 3.5,
          dailyPnl: 3000,
          dailyReturnPct: 2.94,
        },
      ],
    }));

    expect(normalized.rows).toHaveLength(3);
    expect(normalized.rows.map((row) => row.date)).toEqual(['2026-03-01', '2026-03-02', '2026-03-03']);
    expect(normalized.rows[1]).toMatchObject({
      strategyCumReturn: 2,
      benchmarkCumReturn: 1.2,
      buyHoldCumReturn: 1.1,
      dailyPnl: 2000,
      position: 1,
      action: 'buy',
      fillPrice: 101,
      shares: 100,
      cash: 89900,
      totalValue: 102000,
    });
    expect(normalized.viewerMeta.rowCount).toBe(3);
    expect(normalized.viewerMeta.strategySeriesLength).toBe(3);
    expect(normalized.viewerMeta.dailyPnlSeriesLength).toBe(3);
    expect(normalized.viewerMeta.positionSeriesLength).toBe(3);
    expect(normalized.tradeEvents.length).toBeGreaterThanOrEqual(2);
  });

  it('merges curve-only payloads and derives missing strategy returns from total value', () => {
    const normalized = normalizeDeterministicBacktestResult(makeRun({
      totalReturnPct: null,
      finalEquity: null,
      benchmarkReturnPct: null,
      buyAndHoldReturnPct: null,
      equityCurve: [
        { date: '2026-03-01', totalPortfolioValue: 100000, cumulativeReturnPct: 0, exposurePct: 0 },
        { date: '2026-03-02', totalPortfolioValue: 102000, exposurePct: 1, executedAction: 'buy' },
      ],
      dailyReturnSeries: [
        { date: '2026-03-02', dailyPnl: 2000, dailyReturnPct: 2 },
      ],
      benchmarkCurve: [
        { date: '2026-03-02', cumulativeReturnPct: 1.5 },
      ],
      buyAndHoldCurve: [
        { date: '2026-03-02', cumulativeReturnPct: 1.2 },
      ],
      exposureCurve: [
        { date: '2026-03-02', exposure: 1, positionState: 'long' },
      ],
    }));

    expect(normalized.rows).toHaveLength(2);
    expect(normalized.rows[1]?.strategyCumReturn).toBe(2);
    expect(normalized.metrics.totalReturnPct).toBe(2);
    expect(normalized.metrics.finalEquity).toBe(102000);
    expect(normalized.viewerMeta.primaryRowSource).toBe('mergedSeries');
  });
});
