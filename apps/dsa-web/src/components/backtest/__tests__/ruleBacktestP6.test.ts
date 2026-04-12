import { beforeEach, describe, expect, it } from 'vitest';
import type { RuleBacktestRunResponse } from '../../../types/backtest';
import { normalizeDeterministicBacktestResult } from '../normalizeDeterministicBacktestResult';
import {
  RULE_BACKTEST_PRESET_STORAGE_KEY,
  buildRuleRunComparisonWarnings,
  buildRuleRunReportMarkdown,
  createRuleBacktestPresetFromRun,
  getRuleScenarioPlans,
  loadRuleBacktestPresets,
  saveRuleBacktestPreset,
} from '../ruleBacktestP6';

function makeRun(overrides: Partial<RuleBacktestRunResponse> = {}): RuleBacktestRunResponse {
  return {
    id: 501,
    code: 'ORCL',
    strategyText: '5日均线上穿20日均线买入，下穿卖出',
    parsedStrategy: {
      version: 'v1',
      timeframe: 'daily',
      sourceText: '5日均线上穿20日均线买入，下穿卖出',
      normalizedText: 'SMA5 上穿 SMA20 买入，下穿卖出。',
      entry: { type: 'group', op: 'and', rules: [] },
      exit: { type: 'group', op: 'or', rules: [] },
      confidence: 0.92,
      needsConfirmation: false,
      ambiguities: [],
      summary: {
        entry: 'SMA5 上穿 SMA20',
        exit: 'SMA5 下穿 SMA20',
      },
      maxLookback: 20,
      strategyKind: 'moving_average_crossover',
      executable: true,
      normalizationState: 'ready',
      assumptions: [],
      assumptionGroups: [],
      detectedStrategyFamily: 'moving_average_crossover',
      unsupportedReason: null,
      unsupportedDetails: [],
      unsupportedExtensions: [],
      coreIntentSummary: '已识别为均线交叉。',
      interpretationConfidence: 0.92,
      supportedPortionSummary: '均线交叉已支持。',
      rewriteSuggestions: [],
      parseWarnings: [],
      setup: {
        symbol: 'ORCL',
      },
      strategySpec: {
        strategyType: 'moving_average_crossover',
        strategyFamily: 'moving_average_crossover',
        symbol: 'ORCL',
        timeframe: 'daily',
        signal: {
          indicatorFamily: 'moving_average',
          fastPeriod: 5,
          slowPeriod: 20,
          fastType: 'simple',
          slowType: 'simple',
          entryCondition: 'fast_crosses_above_slow',
          exitCondition: 'fast_crosses_below_slow',
        },
        execution: {
          frequency: 'daily',
          signalTiming: 'bar_close',
          fillTiming: 'next_bar_open',
        },
        positionBehavior: {
          direction: 'long_only',
          entrySizing: 'all_available_capital',
          maxPositions: 1,
          pyramiding: false,
        },
        endBehavior: {
          policy: 'liquidate_at_end',
          priceBasis: 'close',
        },
        capital: {
          initialCapital: 100000,
          currency: 'USD',
        },
        costs: {
          feeBps: 0,
          slippageBps: 0,
        },
      },
    } as RuleBacktestRunResponse['parsedStrategy'],
    strategyHash: 'hash',
    timeframe: 'daily',
    startDate: '2026-01-01',
    endDate: '2026-03-31',
    periodStart: '2026-01-01',
    periodEnd: '2026-03-31',
    lookbackBars: 252,
    initialCapital: 100000,
    feeBps: 0,
    slippageBps: 0,
    parsedConfidence: 0.92,
    needsConfirmation: false,
    warnings: [],
    runAt: '2026-04-10T08:00:00Z',
    completedAt: '2026-04-10T08:05:00Z',
    status: 'completed',
    statusMessage: '规则回测已完成。',
    statusHistory: [{ status: 'completed', at: '2026-04-10T08:05:00Z' }],
    noResultReason: null,
    noResultMessage: null,
    tradeCount: 4,
    winCount: 3,
    lossCount: 1,
    totalReturnPct: 12.5,
    annualizedReturnPct: 20.1,
    benchmarkMode: 'auto',
    benchmarkCode: null,
    benchmarkReturnPct: 8.2,
    excessReturnVsBenchmarkPct: 4.3,
    buyAndHoldReturnPct: 7.8,
    excessReturnVsBuyAndHoldPct: 4.7,
    winRatePct: 75,
    avgTradeReturnPct: 3.2,
    maxDrawdownPct: -5.4,
    avgHoldingDays: 8,
    avgHoldingBars: 8,
    avgHoldingCalendarDays: 10,
    finalEquity: 112500,
    summary: {},
    executionModel: {
      timeframe: 'daily',
      feeBpsPerSide: 0,
      slippageBpsPerSide: 0,
    },
    executionAssumptions: {
      signalEvaluationTiming: 'bar close',
      benchmarkMethod: 'market_index',
    },
    benchmarkCurve: [],
    benchmarkSummary: {
      label: 'QQQ',
      resolvedMode: 'etf_qqq',
      requestedMode: 'auto',
      method: 'benchmark_security',
      returnPct: 8.2,
      fallbackUsed: false,
    },
    buyAndHoldCurve: [],
    buyAndHoldSummary: {
      label: '当前标的买入并持有',
      resolvedMode: 'same_symbol_buy_and_hold',
      method: 'same_symbol_buy_and_hold',
      returnPct: 7.8,
    },
    auditRows: [
      {
        date: '2026-01-01',
        cumulativeStrategyReturnPct: 0,
        cumulativeBenchmarkReturnPct: 0,
        cumulativeBuyAndHoldReturnPct: 0,
        totalPortfolioValue: 100000,
        dailyPnl: 0,
        dailyReturnPct: 0,
        drawdownPct: 0,
        targetPosition: 0,
      },
      {
        date: '2026-02-01',
        cumulativeStrategyReturnPct: 6,
        cumulativeBenchmarkReturnPct: 3,
        cumulativeBuyAndHoldReturnPct: 2.8,
        totalPortfolioValue: 106000,
        dailyPnl: 6000,
        dailyReturnPct: 6,
        drawdownPct: -2,
        targetPosition: 1,
        executedAction: 'buy',
      },
      {
        date: '2026-03-31',
        cumulativeStrategyReturnPct: 12.5,
        cumulativeBenchmarkReturnPct: 8.2,
        cumulativeBuyAndHoldReturnPct: 7.8,
        totalPortfolioValue: 112500,
        dailyPnl: 6500,
        dailyReturnPct: 6.13,
        drawdownPct: -5.4,
        targetPosition: 0,
        executedAction: 'sell',
      },
    ],
    dailyReturnSeries: [],
    exposureCurve: [],
    aiSummary: null,
    equityCurve: [],
    trades: [],
    executionTrace: {
      source: 'storedExecutionTrace',
      rows: [],
      assumptionsDefaults: {
        summaryText: 'next bar open / long only',
      },
      fallback: {
        runFallback: false,
        traceRebuilt: false,
        note: '标准执行路径',
      },
    },
    ...overrides,
  };
}

describe('ruleBacktestP6', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('builds comparison warnings and a readable report summary', () => {
    const baseRun = makeRun();
    const compareRun = makeRun({
      id: 502,
      startDate: '2025-01-01',
      endDate: '2025-12-31',
      feeBps: 5,
      slippageBps: 5,
      benchmarkMode: 'none',
    });

    const warnings = buildRuleRunComparisonWarnings([baseRun, compareRun]);
    expect(warnings).toEqual(expect.arrayContaining([
      expect.stringContaining('不同日期区间'),
      expect.stringContaining('手续费或滑点假设不同'),
      expect.stringContaining('不同基准设置'),
    ]));

    const markdown = buildRuleRunReportMarkdown({
      run: baseRun,
      normalized: normalizeDeterministicBacktestResult(baseRun),
      comparedRuns: [compareRun],
    });

    expect(markdown).toContain('确定性回测决策摘要');
    expect(markdown).toContain('总收益：12.50%');
    expect(markdown).toContain('比较提醒');
    expect(markdown).toContain('#502');
  });

  it('creates scenario plans for supported strategies', () => {
    const plans = getRuleScenarioPlans(makeRun());
    const labels = plans.map((plan) => plan.label);

    expect(labels).toContain('基准情景');
    expect(labels).toContain('费用/滑点压力');
    expect(labels).toContain('Lookback 窗口');
    expect(labels).toContain('均线窗口变体');
    expect(plans.find((plan) => plan.id === 'ma_window_variants')?.variants.length).toBeGreaterThan(0);
  });

  it('persists saved presets and deduplicates recent drafts', () => {
    const run = makeRun();
    const savedPreset = createRuleBacktestPresetFromRun(run, { kind: 'saved', name: 'ORCL Swing' });
    const recentPreset = createRuleBacktestPresetFromRun(run, { kind: 'recent' });

    saveRuleBacktestPreset(savedPreset);
    saveRuleBacktestPreset(recentPreset);
    saveRuleBacktestPreset(createRuleBacktestPresetFromRun(run, { kind: 'recent' }));

    const stored = loadRuleBacktestPresets();
    expect(window.localStorage.getItem(RULE_BACKTEST_PRESET_STORAGE_KEY)).toBeTruthy();
    expect(stored.filter((item) => item.kind === 'saved')).toHaveLength(1);
    expect(stored.filter((item) => item.kind === 'recent')).toHaveLength(1);
    expect(stored[0]?.name).toBeTruthy();
  });
});

