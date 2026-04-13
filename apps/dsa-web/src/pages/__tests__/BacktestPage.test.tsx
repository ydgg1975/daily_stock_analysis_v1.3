import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type {
  BacktestRunHistoryItem,
  BacktestRunResponse,
  PrepareBacktestSamplesResponse,
  RuleBacktestParseResponse,
  RuleBacktestRunResponse,
} from '../../types/backtest';
import { RULE_BACKTEST_PRESET_STORAGE_KEY } from '../../components/backtest/ruleBacktestP6';
import BacktestPage from '../BacktestPage';
import DeterministicBacktestResultPage from '../DeterministicBacktestResultPage';

const {
  runBacktest,
  getResults,
  getOverallPerformance,
  getStockPerformance,
  prepareSamples,
  getHistory,
  getSampleStatus,
  clearSamples,
  clearResults,
  parseRuleStrategy,
  runRuleBacktest,
  getRuleBacktestRuns,
  getRuleBacktestRun,
  getRuleBacktestRunStatus,
  cancelRuleBacktestRun,
} = vi.hoisted(() => ({
  runBacktest: vi.fn(),
  getResults: vi.fn(),
  getOverallPerformance: vi.fn(),
  getStockPerformance: vi.fn(),
  prepareSamples: vi.fn(),
  getHistory: vi.fn(),
  getSampleStatus: vi.fn(),
  clearSamples: vi.fn(),
  clearResults: vi.fn(),
  parseRuleStrategy: vi.fn(),
  runRuleBacktest: vi.fn(),
  getRuleBacktestRuns: vi.fn(),
  getRuleBacktestRun: vi.fn(),
  getRuleBacktestRunStatus: vi.fn(),
  cancelRuleBacktestRun: vi.fn(),
}));

vi.mock('motion/react', async () => {
  const React = await import('react');
  type StaticMotionDivProps = React.HTMLAttributes<HTMLDivElement> & {
    children?: React.ReactNode;
    animate?: unknown;
    exit?: unknown;
    initial?: unknown;
    layout?: unknown;
    transition?: unknown;
    variants?: unknown;
    whileHover?: unknown;
    whileTap?: unknown;
  };

  const StaticDiv = React.forwardRef<HTMLDivElement, StaticMotionDivProps>(
    ({ children, ...props }, ref) => {
      const rest = { ...props } as Record<string, unknown>;
      delete rest.animate;
      delete rest.exit;
      delete rest.initial;
      delete rest.layout;
      delete rest.transition;
      delete rest.variants;
      delete rest.whileHover;
      delete rest.whileTap;
      return React.createElement('div', { ...rest, ref }, children);
    },
  );
  StaticDiv.displayName = 'StaticMotionDiv';

  return {
    AnimatePresence: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
    motion: {
      div: StaticDiv,
      section: StaticDiv,
    },
  };
});

vi.mock('../../api/backtest', () => ({
  backtestApi: {
    run: runBacktest,
    getResults,
    getOverallPerformance,
    getStockPerformance,
    prepareSamples,
    getHistory,
    getSampleStatus,
    clearSamples,
    clearResults,
    parseRuleStrategy,
    runRuleBacktest,
    getRuleBacktestRuns,
    getRuleBacktestRun,
    getRuleBacktestRunStatus,
    cancelRuleBacktestRun,
  },
}));

function renderBacktestRoutes(
  initialEntries: Array<string | { pathname: string; state?: unknown }> = ['/backtest'],
) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="/backtest/results/:runId" element={<DeterministicBacktestResultPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function makeRunResponse(overrides: Partial<BacktestRunResponse> = {}): BacktestRunResponse {
  return {
    runId: 1,
    runAt: '2026-04-07T08:00:00Z',
    processed: 1,
    saved: 1,
    completed: 1,
    insufficient: 0,
    errors: 0,
    candidateCount: 1,
    noResultReason: null,
    noResultMessage: null,
    evaluationMode: 'historical_analysis_evaluation',
    requestedMode: 'local_first',
    resolvedSource: 'LocalParquet',
    fallbackUsed: false,
    evaluationWindowTradingBars: 10,
    maturityCalendarDays: 14,
    executionAssumptions: {
      moduleType: 'historical_analysis_evaluation',
      priceBasis: 'close',
    },
    ...overrides,
  };
}

function makeHistoryItem(): BacktestRunHistoryItem {
  return {
    id: 1,
    code: 'ORCL',
    evalWindowDays: 10,
    evaluationWindowTradingBars: 10,
    minAgeDays: 14,
    maturityCalendarDays: 14,
    force: false,
    runAt: '2026-04-07T08:00:00Z',
    completedAt: '2026-04-07T08:00:00Z',
    processed: 1,
    saved: 1,
    completed: 1,
    insufficient: 0,
    errors: 0,
    candidateCount: 1,
    resultCount: 1,
    noResultReason: null,
    noResultMessage: null,
    status: 'completed',
    totalEvaluations: 1,
    completedCount: 1,
    insufficientCount: 0,
    longCount: 1,
    cashCount: 0,
    winCount: 1,
    lossCount: 0,
    neutralCount: 0,
    winRatePct: 100,
    avgStockReturnPct: 6,
    avgSimulatedReturnPct: 10,
    directionAccuracyPct: 100,
    summary: {},
    evaluationMode: 'historical_analysis_evaluation',
    requestedMode: 'local_first',
    resolvedSource: 'LocalParquet',
    fallbackUsed: false,
    executionAssumptions: {
      moduleType: 'historical_analysis_evaluation',
    },
  };
}

function makeRuleParseResponse(): RuleBacktestParseResponse {
  return {
    code: 'ORCL',
    strategyText: '资金100000，从2025-01-01到2025-12-31，每天买100股ORCL，买到资金耗尽为止',
    normalizedStrategyFamily: 'periodic_accumulation',
    executable: true,
    normalizationState: 'assumed',
    assumptions: [
      { key: 'fill_timing', label: '成交时点', value: '当日开盘价', reason: '按定投计划在交易日开盘执行。' },
    ],
    assumptionGroups: [
      {
        key: 'execution_defaults',
        label: '执行默认值',
        items: [
          { key: 'fill_timing', label: '成交时点', value: '当日开盘价', reason: '按定投计划在交易日开盘执行。' },
        ],
      },
    ],
    detectedStrategyFamily: 'periodic_accumulation',
    unsupportedReason: null,
    unsupportedDetails: [],
    unsupportedExtensions: [],
    coreIntentSummary: '已识别为单标的区间定投：ORCL，按固定频率买入。',
    interpretationConfidence: 0.97,
    supportedPortionSummary: '已识别为单标的区间定投规则。',
    rewriteSuggestions: [],
    parseWarnings: [],
    parsedStrategy: {
      version: 'v1',
      timeframe: 'daily',
      sourceText: '资金100000，从2025-01-01到2025-12-31，每天买100股ORCL，买到资金耗尽为止',
      normalizedText: '资金 100000，2025-01-01 至 2025-12-31，每个交易日买入 100 股 ORCL，现金不足即停止买入。',
      entry: { type: 'group', op: 'and', rules: [] },
      exit: { type: 'group', op: 'or', rules: [] },
      confidence: 0.97,
      needsConfirmation: false,
      ambiguities: [],
      summary: {
        entry: '每个交易日买入 100 股 ORCL',
        exit: '区间结束统一按收盘价平仓',
        strategy: '中文定投策略草稿',
      },
      maxLookback: 1,
      strategyKind: 'periodic_accumulation',
      executable: true,
      normalizationState: 'assumed',
      assumptions: [
        { key: 'fill_timing', label: '成交时点', value: '当日开盘价', reason: '按定投计划在交易日开盘执行。' },
      ],
      assumptionGroups: [
        {
          key: 'execution_defaults',
          label: '执行默认值',
          items: [
            { key: 'fill_timing', label: '成交时点', value: '当日开盘价', reason: '按定投计划在交易日开盘执行。' },
          ],
        },
      ],
      detectedStrategyFamily: 'periodic_accumulation',
      unsupportedReason: null,
      unsupportedDetails: [],
      unsupportedExtensions: [],
      coreIntentSummary: '已识别为单标的区间定投：ORCL，按固定频率买入。',
      interpretationConfidence: 0.97,
      supportedPortionSummary: '已识别为单标的区间定投规则。',
      rewriteSuggestions: [],
      parseWarnings: [],
      setup: {
        symbol: 'ORCL',
        startDate: '2025-01-01',
        endDate: '2025-12-31',
        initialCapital: 100000,
        executionFrequency: 'daily',
        action: 'buy',
        orderMode: 'fixed_shares',
        quantityPerTrade: 100,
        cashPolicy: 'stop_when_insufficient_cash',
        executionPriceBasis: 'open',
        feeBps: 0,
        slippageBps: 0,
        exitPolicy: 'close_at_end',
      },
      strategySpec: {
        strategyType: 'periodic_accumulation',
        version: 'v1',
        symbol: 'ORCL',
        timeframe: 'daily',
        dateRange: {
          startDate: '2025-01-01',
          endDate: '2025-12-31',
        },
        capital: {
          initialCapital: 100000,
          currency: 'USD',
        },
        schedule: {
          frequency: 'daily',
          timing: 'session_open',
        },
        entry: {
          side: 'buy',
          order: {
            mode: 'fixed_shares',
            quantity: 100,
            amount: null,
          },
          priceBasis: 'open',
        },
        exit: {
          policy: 'close_at_end',
          priceBasis: 'close',
        },
        positionBehavior: {
          accumulate: true,
          cashPolicy: 'stop_when_insufficient_cash',
        },
        costs: {
          feeBps: 0,
          slippageBps: 0,
        },
      },
    },
    confidence: 0.97,
    needsConfirmation: true,
    ambiguities: [],
    summary: {
      entry: '每个交易日买入 100 股 ORCL',
      exit: '区间结束统一按收盘价平仓',
      strategy: '中文定投策略草稿',
    },
    maxLookback: 1,
  };
}

function makeUnsupportedMacdParseResponse(): RuleBacktestParseResponse {
  return {
    code: 'AAPL',
    strategyText: 'MACD金叉买入，止损5%，死叉卖出',
    normalizedStrategyFamily: 'macd_crossover',
    executable: false,
    normalizationState: 'unsupported',
    assumptions: [],
    assumptionGroups: [],
    detectedStrategyFamily: 'macd_crossover',
    unsupportedReason: '当前已支持 MACD 主规则，但不支持叠加固定止损 / 止盈 / trailing stop。',
    unsupportedDetails: [
      { code: 'unsupported_strategy_combination', title: '组合执行语义', message: '当前已支持技术信号主规则，但不支持叠加固定止损 / 止盈 / trailing stop。' },
    ],
    unsupportedExtensions: [
      { code: 'unsupported_strategy_combination', title: '组合执行语义', message: '当前已支持技术信号主规则，但不支持叠加固定止损 / 止盈 / trailing stop。' },
    ],
    coreIntentSummary: '已识别为 MACD 金叉 / 死叉主规则。',
    interpretationConfidence: 0.9,
    supportedPortionSummary: '已识别为 MACD 金叉 / 死叉主规则。',
    rewriteSuggestions: [
      { label: '改写成当前可执行版本', strategyText: 'AAPL，MACD金叉买入，死叉卖出' },
    ],
    parseWarnings: [
      { code: 'default_macd_periods', message: '未显式写出 MACD 参数，当前默认使用 (12, 26, 9)。' },
    ],
    parsedStrategy: {
      version: 'v1',
      timeframe: 'daily',
      sourceText: 'MACD金叉买入，止损5%，死叉卖出',
      normalizedText: 'MACD(12,26,9) 金叉买入，MACD(12,26,9) 死叉卖出。',
      entry: { type: 'group', op: 'and', rules: [] },
      exit: { type: 'group', op: 'or', rules: [] },
      confidence: 0.96,
      needsConfirmation: true,
      ambiguities: [],
      summary: {
        entry: '买入条件：MACD(12,26,9) 金叉',
        exit: '卖出条件：MACD(12,26,9) 死叉',
        strategy: 'MACD 交叉策略',
      },
      maxLookback: 35,
      strategyKind: 'macd_crossover',
      executable: false,
      normalizationState: 'unsupported',
      assumptions: [],
      assumptionGroups: [],
      detectedStrategyFamily: 'macd_crossover',
      unsupportedReason: '当前已支持 MACD 主规则，但不支持叠加固定止损 / 止盈 / trailing stop。',
      unsupportedDetails: [
        { code: 'unsupported_strategy_combination', title: '组合执行语义', message: '当前已支持技术信号主规则，但不支持叠加固定止损 / 止盈 / trailing stop。' },
      ],
      unsupportedExtensions: [
        { code: 'unsupported_strategy_combination', title: '组合执行语义', message: '当前已支持技术信号主规则，但不支持叠加固定止损 / 止盈 / trailing stop。' },
      ],
      coreIntentSummary: '已识别为 MACD 金叉 / 死叉主规则。',
      interpretationConfidence: 0.9,
      supportedPortionSummary: '已识别为 MACD 金叉 / 死叉主规则。',
      rewriteSuggestions: [
        { label: '改写成当前可执行版本', strategyText: 'AAPL，MACD金叉买入，死叉卖出' },
      ],
      parseWarnings: [
        { code: 'default_macd_periods', message: '未显式写出 MACD 参数，当前默认使用 (12, 26, 9)。' },
      ],
      strategySpec: {
        strategyType: 'macd_crossover',
        symbol: 'AAPL',
      },
    },
    confidence: 0.96,
    needsConfirmation: true,
    ambiguities: [],
    summary: {
      entry: '买入条件：MACD(12,26,9) 金叉',
      exit: '卖出条件：MACD(12,26,9) 死叉',
      strategy: 'MACD 交叉策略',
    },
    maxLookback: 35,
  };
}

function makeLegacySetupOnlyParseResponse(): RuleBacktestParseResponse {
  const response = makeRuleParseResponse();
  return {
    ...response,
    parsedStrategy: {
      ...response.parsedStrategy,
      strategySpec: undefined,
    },
  };
}

function makeRuleRunResponse(overrides: Partial<RuleBacktestRunResponse> = {}): RuleBacktestRunResponse {
  return {
    id: 99,
    code: 'ORCL',
    strategyText: '资金100000，从2025-01-01到2025-12-31，每天买100股ORCL，买到资金耗尽为止',
    parsedStrategy: makeRuleParseResponse().parsedStrategy,
    strategyHash: 'hash',
    timeframe: 'daily',
    startDate: '2025-01-01',
    endDate: '2025-12-31',
    periodStart: '2025-01-01',
    periodEnd: '2025-12-31',
    lookbackBars: 252,
    initialCapital: 100000,
    feeBps: 0,
    slippageBps: 0,
    parsedConfidence: 0.97,
    needsConfirmation: true,
    warnings: [],
    runAt: '2026-04-07T08:00:00Z',
    completedAt: null,
    status: 'queued',
    statusMessage: '策略已提交，等待开始执行。',
    statusHistory: [
      { status: 'queued', at: '2026-04-07T08:00:00Z' },
    ],
    noResultReason: null,
    noResultMessage: null,
    tradeCount: 0,
    winCount: 0,
    lossCount: 0,
    totalReturnPct: 0,
    annualizedReturnPct: 0,
    benchmarkMode: 'auto',
    benchmarkCode: null,
    benchmarkReturnPct: null,
    excessReturnVsBenchmarkPct: null,
    buyAndHoldReturnPct: 0,
    excessReturnVsBuyAndHoldPct: 0,
    winRatePct: 0,
    avgTradeReturnPct: 0,
    maxDrawdownPct: 0,
    avgHoldingDays: 0,
    avgHoldingBars: 0,
    avgHoldingCalendarDays: 0,
    finalEquity: 100000,
    summary: {
      parsedStrategySummary: makeRuleParseResponse().summary,
    },
    executionAssumptions: {
      priceBasis: 'close',
      signalEvaluationTiming: 'bar close',
      entryFillTiming: 'next bar open',
      positionSizing: 'all_available_capital',
    },
    benchmarkCurve: [],
    benchmarkSummary: {
      label: '当前标的买入并持有',
      requestedMode: 'auto',
      resolvedMode: 'same_symbol_buy_and_hold',
      method: 'same_symbol_buy_and_hold',
      priceBasis: 'close',
      startDate: '2025-01-01',
      endDate: '2025-12-31',
      returnPct: 0,
    },
    buyAndHoldCurve: [],
    buyAndHoldSummary: {
      label: '当前标的买入并持有',
      requestedMode: 'same_symbol_buy_and_hold',
      resolvedMode: 'same_symbol_buy_and_hold',
      method: 'same_symbol_buy_and_hold',
      priceBasis: 'close',
      startDate: '2025-01-01',
      endDate: '2025-12-31',
      returnPct: 0,
    },
    auditRows: [
      {
        date: '2025-01-01',
        targetPosition: 0,
        totalPortfolioValue: 100000,
        cumulativeStrategyReturnPct: 0,
        cumulativeBenchmarkReturnPct: 0,
        cumulativeBuyAndHoldReturnPct: 0,
        dailyPnl: 0,
        dailyReturnPct: 0,
        drawdownPct: 0,
      },
      {
        date: '2025-06-01',
        targetPosition: 1,
        executedAction: 'buy',
        fillPrice: 50,
        totalPortfolioValue: 103000,
        cumulativeStrategyReturnPct: 3,
        cumulativeBenchmarkReturnPct: 1.8,
        cumulativeBuyAndHoldReturnPct: 1.6,
        dailyPnl: 3000,
        dailyReturnPct: 3,
        drawdownPct: -1.2,
      },
      {
        date: '2025-12-31',
        targetPosition: 0,
        executedAction: 'sell',
        fillPrice: 55,
        totalPortfolioValue: 108000,
        cumulativeStrategyReturnPct: 8,
        cumulativeBenchmarkReturnPct: 4.2,
        cumulativeBuyAndHoldReturnPct: 3.9,
        dailyPnl: 5000,
        dailyReturnPct: 4.85,
        drawdownPct: -2.4,
      },
    ],
    dailyReturnSeries: [],
    exposureCurve: [],
    aiSummary: null,
    equityCurve: [],
    trades: [],
    ...overrides,
  };
}

describe('BacktestPage', () => {
  async function openDeterministicStrategyInput() {
    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole('button', { name: '继续' }));
    expect(screen.getByTestId('backtest-control-section-setup')).toHaveAttribute('data-active', 'true');
  }

  async function parseDeterministicStrategy() {
    await openDeterministicStrategyInput();
    fireEvent.click(screen.getByRole('button', { name: '解析策略' }));
    expect(await screen.findByTestId('confirm-status-section')).toBeInTheDocument();
  }

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();

    getResults.mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    getHistory.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [makeHistoryItem()],
    });
    getSampleStatus.mockResolvedValue({
      code: 'ORCL',
      preparedCount: 8,
      preparedStartDate: '2026-03-01',
      preparedEndDate: '2026-03-18',
      latestPreparedAt: '2026-04-07T08:00:00Z',
      latestPreparedSampleDate: '2026-03-18',
      latestEligibleSampleDate: '2026-03-18',
      excludedRecentReason: 'evaluation_window_not_satisfied',
      excludedRecentMessage: '最新行情到 2026-04-07，但评估需要完整的 10 根未来窗口，所以最新可用于样本生成的日期只到 2026-03-18。',
      evalWindowDays: 10,
      minAgeDays: 14,
      requestedMode: 'local_first',
      resolvedSource: 'LocalParquet',
      fallbackUsed: false,
      pricingResolvedSource: 'LocalParquet',
      pricingFallbackUsed: false,
      evaluationWindowTradingBars: 10,
      maturityCalendarDays: 14,
    });
    clearSamples.mockResolvedValue({
      code: 'ORCL',
      deletedRuns: 0,
      deletedResults: 0,
      deletedSamples: 0,
      deletedSummaries: 0,
      message: 'ok',
    });
    clearResults.mockResolvedValue({
      code: 'ORCL',
      deletedRuns: 0,
      deletedResults: 0,
      deletedSamples: 0,
      deletedSummaries: 0,
      message: 'ok',
    });
    getOverallPerformance.mockResolvedValue(null);
    getStockPerformance.mockResolvedValue(null);
    prepareSamples.mockResolvedValue({
      code: 'ORCL',
      sampleCount: 60,
      prepared: 4,
      skippedExisting: 2,
      marketRowsSaved: 10,
      candidateRows: 12,
      evalWindowDays: 10,
      minAgeDays: 14,
      preparedStartDate: '2026-03-01',
      preparedEndDate: '2026-03-18',
      latestPreparedAt: '2026-04-07T08:00:00Z',
      noResultReason: null,
      noResultMessage: '已准备 4 条历史分析评估样本，可重新运行评估。',
      requestedMode: 'local_first',
      resolvedSource: 'LocalParquet',
      fallbackUsed: false,
      evaluationWindowTradingBars: 10,
      maturityCalendarDays: 14,
    } satisfies PrepareBacktestSamplesResponse);
    runBacktest.mockResolvedValue(makeRunResponse());
    parseRuleStrategy.mockResolvedValue(makeRuleParseResponse());
    runRuleBacktest.mockResolvedValue(makeRuleRunResponse());
    getRuleBacktestRuns.mockResolvedValue({
      total: 0,
      page: 1,
      limit: 10,
      items: [],
    });
    getRuleBacktestRun.mockResolvedValue(
      makeRuleRunResponse({
        status: 'completed',
        statusMessage: '规则回测已完成，可查看交易明细与执行假设。',
        completedAt: '2026-04-07T08:02:00Z',
        statusHistory: [
          { status: 'queued', at: '2026-04-07T08:00:00Z' },
          { status: 'running', at: '2026-04-07T08:00:30Z' },
          { status: 'summarizing', at: '2026-04-07T08:01:30Z' },
          { status: 'completed', at: '2026-04-07T08:02:00Z' },
        ],
        tradeCount: 2,
        winCount: 1,
        lossCount: 1,
        totalReturnPct: 8.5,
        annualizedReturnPct: 12.4,
        benchmarkMode: 'auto',
        benchmarkCode: null,
        benchmarkReturnPct: 6.4,
        excessReturnVsBenchmarkPct: 2.1,
        buyAndHoldReturnPct: 5.2,
        excessReturnVsBuyAndHoldPct: 3.3,
        winRatePct: 50,
        avgTradeReturnPct: 4.25,
        maxDrawdownPct: 3.2,
        avgHoldingDays: 6,
        avgHoldingBars: 5.5,
        avgHoldingCalendarDays: 6,
        finalEquity: 108500,
        aiSummary: '该策略相对 buy-and-hold 取得了正向超额收益，但交易样本仍然较少。',
        equityCurve: [
          { date: '2026-03-01', equity: 100000, cumulativeReturnPct: 0, drawdownPct: 0 },
          { date: '2026-03-10', equity: 103200, cumulativeReturnPct: 3.2, drawdownPct: -1.1 },
          { date: '2026-03-18', equity: 108500, cumulativeReturnPct: 8.5, drawdownPct: 0 },
        ],
        benchmarkCurve: [
          { date: '2026-03-01', close: 100, normalizedValue: 1, cumulativeReturnPct: 0 },
          { date: '2026-03-10', close: 103.1, normalizedValue: 1.031, cumulativeReturnPct: 3.1 },
          { date: '2026-03-18', close: 106.4, normalizedValue: 1.064, cumulativeReturnPct: 6.4 },
        ],
        benchmarkSummary: {
          label: 'QQQ',
          requestedMode: 'auto',
          resolvedMode: 'etf_qqq',
          code: 'QQQ',
          autoResolved: true,
          method: 'benchmark_security',
          priceBasis: 'close',
          startDate: '2026-03-01',
          endDate: '2026-03-18',
          startPrice: 100,
          endPrice: 106.4,
          returnPct: 6.4,
        },
        buyAndHoldCurve: [
          { date: '2026-03-01', close: 100, normalizedValue: 1, cumulativeReturnPct: 0 },
          { date: '2026-03-10', close: 102, normalizedValue: 1.02, cumulativeReturnPct: 2 },
          { date: '2026-03-18', close: 105.2, normalizedValue: 1.052, cumulativeReturnPct: 5.2 },
        ],
        buyAndHoldSummary: {
          label: '当前标的买入并持有',
          requestedMode: 'same_symbol_buy_and_hold',
          resolvedMode: 'same_symbol_buy_and_hold',
          method: 'same_symbol_buy_and_hold',
          priceBasis: 'close',
          startDate: '2026-03-01',
          endDate: '2026-03-18',
          startPrice: 100,
          endPrice: 105.2,
          returnPct: 5.2,
        },
        auditRows: [
          {
            date: '2026-03-01',
            symbolClose: 100,
            benchmarkClose: 100,
            signalSummary: '等待开仓信号',
            targetPosition: 0,
            executedAction: null,
            fillPrice: null,
            sharesHeld: 0,
            cash: 100000,
            holdingsValue: 0,
            totalPortfolioValue: 100000,
            dailyPnl: 0,
            dailyReturnPct: 0,
            cumulativeStrategyReturnPct: 0,
            cumulativeBenchmarkReturnPct: 0,
            cumulativeBuyAndHoldReturnPct: 0,
            fees: 0,
            slippage: 0,
            notes: null,
            unavailableReason: null,
          },
          {
            date: '2026-03-10',
            symbolClose: 102,
            benchmarkClose: 103.1,
            signalSummary: 'MA5 > MA20',
            targetPosition: 1,
            executedAction: 'buy',
            fillPrice: 100,
            sharesHeld: 1000,
            cash: 3200,
            holdingsValue: 100000,
            totalPortfolioValue: 103200,
            dailyPnl: 3200,
            dailyReturnPct: 3.2,
            cumulativeStrategyReturnPct: 3.2,
            cumulativeBenchmarkReturnPct: 3.1,
            cumulativeBuyAndHoldReturnPct: 2,
            fees: 0,
            slippage: 0,
            notes: null,
            unavailableReason: null,
          },
          {
            date: '2026-03-18',
            symbolClose: 105.2,
            benchmarkClose: 106.4,
            signalSummary: 'RSI6 > 70',
            targetPosition: 0,
            executedAction: 'sell',
            fillPrice: 106,
            sharesHeld: 0,
            cash: 108500,
            holdingsValue: 0,
            totalPortfolioValue: 108500,
            dailyPnl: 5300,
            dailyReturnPct: 5.135659,
            cumulativeStrategyReturnPct: 8.5,
            cumulativeBenchmarkReturnPct: 6.4,
            cumulativeBuyAndHoldReturnPct: 5.2,
            fees: 0,
            slippage: 0,
            notes: null,
            unavailableReason: null,
          },
        ],
        dailyReturnSeries: [
          { date: '2026-03-01', equity: 100000, dailyReturnPct: 0, dailyPnl: 0 },
          { date: '2026-03-10', equity: 103200, dailyReturnPct: 3.2, dailyPnl: 3200 },
          { date: '2026-03-18', equity: 108500, dailyReturnPct: 5.135659, dailyPnl: 5300 },
        ],
        exposureCurve: [
          { date: '2026-03-01', exposure: 0, positionState: 'flat' },
          { date: '2026-03-10', exposure: 1, positionState: 'long' },
          { date: '2026-03-18', exposure: 0, positionState: 'flat' },
        ],
        trades: [
          {
            code: 'ORCL',
            entryDate: '2026-03-03',
            exitDate: '2026-03-07',
            entrySignalDate: '2026-03-02',
            exitSignalDate: '2026-03-06',
            entryPrice: 100,
            exitPrice: 106,
            entrySignal: '买入条件：MA5 > MA20 且 RSI6 < 40',
            exitSignal: '卖出条件：MA5 < MA20 或 RSI6 > 70',
            entryTrigger: 'MA5 > MA20',
            exitTrigger: 'RSI6 > 70',
            returnPct: 6,
            holdingDays: 5,
            holdingBars: 4,
            holdingCalendarDays: 5,
            entryRule: makeRuleParseResponse().parsedStrategy.entry,
            exitRule: makeRuleParseResponse().parsedStrategy.exit,
            entryIndicators: { ma5: 101.1, ma20: 99.3 },
            exitIndicators: { rsi6: 72.4 },
            entryFillBasis: 'next_bar_open',
            exitFillBasis: 'next_bar_open',
            signalPriceBasis: 'close',
            priceBasis: 'close',
            feeBps: 0,
            slippageBps: 0,
            entryFeeAmount: 0,
            exitFeeAmount: 0,
            entrySlippageAmount: 0,
            exitSlippageAmount: 0,
            notes: null,
          },
        ],
      }),
    );
    getRuleBacktestRunStatus.mockResolvedValue({
      id: 99,
      code: 'ORCL',
      status: 'completed',
      statusMessage: '规则回测已完成，可查看交易明细与执行假设。',
      statusHistory: [
        { status: 'queued', at: '2026-04-07T08:00:00Z' },
        { status: 'running', at: '2026-04-07T08:00:30Z' },
        { status: 'summarizing', at: '2026-04-07T08:01:30Z' },
        { status: 'completed', at: '2026-04-07T08:02:00Z' },
      ],
      runAt: '2026-04-07T08:00:00Z',
      completedAt: '2026-04-07T08:02:00Z',
      noResultReason: null,
      noResultMessage: null,
      tradeCount: 2,
      parsedConfidence: 0.97,
      needsConfirmation: true,
    });
    cancelRuleBacktestRun.mockResolvedValue({
      id: 99,
      code: 'ORCL',
      status: 'cancelled',
      statusMessage: '规则回测已取消。',
      statusHistory: [
        { status: 'queued', at: '2026-04-07T08:00:00Z' },
        { status: 'cancelled', at: '2026-04-07T08:00:45Z' },
      ],
      runAt: '2026-04-07T08:00:00Z',
      completedAt: '2026-04-07T08:00:45Z',
      noResultReason: 'cancelled',
      noResultMessage: '规则回测已取消。',
      tradeCount: 0,
      parsedConfidence: 0.97,
      needsConfirmation: true,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('defaults to Normal Mode and keeps /backtest focused on deterministic configuration', async () => {
    renderBacktestRoutes();

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    expect(screen.getByTestId('backtest-v1-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '回测' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '确定性回测' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '历史评估' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '普通' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: '专业' })).toHaveAttribute('aria-selected', 'false');

    expect(screen.getByTestId('backtest-normal-wizard')).toBeInTheDocument();
    expect(screen.queryByTestId('backtest-unified-shell')).not.toBeInTheDocument();
    expect(screen.queryByTestId('backtest-display-board')).not.toBeInTheDocument();
    expect(screen.queryByTestId('deterministic-backtest-chart-workspace')).not.toBeInTheDocument();
    expect(screen.getByText('普通版配置')).toBeInTheDocument();
    expect(screen.getByText(/运行后会跳转到独立结果页/i)).toBeInTheDocument();

    const activeStage = screen.getByTestId('backtest-normal-active-stage');
    expect(within(activeStage).getByTestId('backtest-control-section-symbol')).toHaveAttribute('data-active', 'true');
    expect(screen.getByTestId('backtest-base-params-layout')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-base-date-range')).toBeInTheDocument();
    expect(screen.getByLabelText('对比基准')).toBeInTheDocument();
    expect(screen.queryByTestId('backtest-control-section-setup')).not.toBeInTheDocument();
    expect(screen.queryByTestId('backtest-control-section-strategy')).not.toBeInTheDocument();
    expect(screen.queryByTestId('backtest-control-section-run')).not.toBeInTheDocument();
    expect(screen.getByTestId('backtest-normal-step-summaries')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-normal-step-summary-setup')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-display-section-history')).toBeInTheDocument();
  });

  it('prefills the symbol when navigated from scanner context', async () => {
    renderBacktestRoutes([{ pathname: '/backtest', state: { prefillCode: '600001', prefillName: '算力龙头' } }]);

    expect(await screen.findByDisplayValue('600001')).toBeInTheDocument();
  });

  it('updates the visible deterministic step in Normal Mode', async () => {
    renderBacktestRoutes();

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: '继续' }));
    expect(screen.getByTestId('backtest-control-section-setup')).toHaveAttribute('data-active', 'true');
    expect(screen.queryByTestId('backtest-control-section-symbol')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '解析策略' }));
    expect(await screen.findByTestId('backtest-control-section-strategy')).toHaveAttribute('data-active', 'true');
    expect(screen.queryByTestId('backtest-control-section-setup')).not.toBeInTheDocument();
    expect(screen.queryByTestId('deterministic-backtest-chart-workspace')).not.toBeInTheDocument();
  });

  it('marks parsed strategy stale after setup changes', async () => {
    renderBacktestRoutes();

    await parseDeterministicStrategy();
    expect(screen.getByText('确认当前解析')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('backtest-normal-step-summary-symbol'));
    fireEvent.change(screen.getByLabelText('结束日期'), { target: { value: '2025-11-30' } });

    fireEvent.click(within(screen.getByLabelText('确定性回测向导步骤')).getByRole('button', { name: /策略确认/i }));
    expect(await screen.findByText('输入已变更。请重新解析后再继续。')).toBeInTheDocument();
  });

  it('shows unsupported guidance and applies rewrite suggestions', async () => {
    parseRuleStrategy.mockResolvedValueOnce(makeUnsupportedMacdParseResponse());

    renderBacktestRoutes();

    await openDeterministicStrategyInput();
    fireEvent.change(screen.getByLabelText('策略文本'), { target: { value: 'MACD金叉买入，止损5%，死叉卖出' } });
    fireEvent.click(screen.getByRole('button', { name: '解析策略' }));

    const guidanceSection = await screen.findByTestId('confirm-guidance-section');
    const assumptionsSection = screen.getByTestId('confirm-assumptions-section');
    expect(screen.getAllByText('当前不支持').length).toBeGreaterThan(0);
    expect(within(assumptionsSection).getByText('推断与提醒')).toBeInTheDocument();
    expect(within(assumptionsSection).getByText('未显式写出 MACD 参数，当前默认使用 (12, 26, 9)。')).toBeInTheDocument();

    fireEvent.click(within(guidanceSection).getByRole('button', {
      name: /改写成当前可执行版本:\s*AAPL，MACD金叉买入，死叉卖出/i,
    }));

    expect(await screen.findByText('已应用建议改写')).toBeInTheDocument();
    expect(screen.getByDisplayValue('AAPL，MACD金叉买入，死叉卖出')).toBeInTheDocument();
  });

  it('keeps parse confirmation and history entry on the configuration page without embedding result analysis', async () => {
    renderBacktestRoutes();

    await parseDeterministicStrategy();

    expect(screen.getByTestId('confirm-status-section')).toBeInTheDocument();
    expect(screen.getByTestId('confirm-compact-summary-section')).toBeInTheDocument();
    const executableSpecSection = screen.getByTestId('confirm-executable-spec-section');
    expect(executableSpecSection).toBeInTheDocument();
    expect(within(executableSpecSection).getByText('实际执行内容')).toBeInTheDocument();
    expect(within(executableSpecSection).getByText('规格来源 · 显式 strategy_spec')).toBeInTheDocument();
    expect(within(executableSpecSection).getAllByText('显式结构化').length).toBeGreaterThan(0);
    expect(within(executableSpecSection).getAllByText('默认/推断').length).toBeGreaterThan(0);
    expect(within(executableSpecSection).getByText('每个交易日')).toBeInTheDocument();
    expect(within(executableSpecSection).getByText('100 股 / 次')).toBeInTheDocument();
    expect(screen.getByText('查看解析细节')).toBeInTheDocument();
    expect(screen.getByTestId('confirm-assumptions-section')).toBeInTheDocument();
    expect(screen.getByText('默认补全与提醒')).toBeInTheDocument();
    expect(screen.queryByTestId('backtest-display-board')).not.toBeInTheDocument();
    expect(screen.getAllByLabelText(/我已确认当前解析结果与执行假设/i)).toHaveLength(1);
    expect(screen.getByTestId('backtest-display-section-history')).toBeInTheDocument();
    expect(screen.queryByTestId('deterministic-backtest-chart-workspace')).not.toBeInTheDocument();
  });

  it('marks executable spec fields as compatibility-derived when only legacy setup is available', async () => {
    parseRuleStrategy.mockResolvedValueOnce(makeLegacySetupOnlyParseResponse());

    renderBacktestRoutes();

    await parseDeterministicStrategy();

    const executableSpecSection = screen.getByTestId('confirm-executable-spec-section');
    expect(within(executableSpecSection).getByText('规格来源 · 兼容 setup')).toBeInTheDocument();
    expect(within(executableSpecSection).getAllByText('兼容 setup').length).toBeGreaterThan(1);
  });

  it('keeps historical evaluation functional across Normal and Professional modes', async () => {
    renderBacktestRoutes();

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('tab', { name: '历史评估' }));

    const unifiedShell = await screen.findByTestId('backtest-unified-shell');
    expect(unifiedShell).toHaveAttribute('data-module', 'historical');
    expect(screen.getByRole('tab', { name: '普通' })).toHaveAttribute('aria-selected', 'true');

    const controlPanel = screen.getByTestId('backtest-control-panel');
    const displayBoard = screen.getByTestId('backtest-display-board');
    expect(screen.getByTestId('backtest-control-window')).toBeInTheDocument();

    expect(within(screen.getByTestId('historical-control-section-scope-samples')).getByText('范围与样本')).toBeInTheDocument();
    expect(screen.queryByTestId('historical-control-section-params')).not.toBeInTheDocument();
    expect(screen.queryByTestId('historical-control-section-execute')).not.toBeInTheDocument();
    expect(screen.queryByTestId('historical-control-section-results')).not.toBeInTheDocument();

    expect(within(displayBoard).getByText('评估概览')).toBeInTheDocument();
    expect(within(displayBoard).getByText('评估结果')).toBeInTheDocument();
    expect(within(displayBoard).getByText('历史记录')).toBeInTheDocument();
    expect(within(displayBoard).queryByRole('button', { name: '运行历史评估' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '专业' }));
    expect(screen.getByTestId('backtest-control-panel-expanded')).toBeInTheDocument();
    expect(within(controlPanel).getByTestId('historical-control-section-scope-samples')).toBeInTheDocument();
    expect(within(controlPanel).getByTestId('historical-control-section-params')).toBeInTheDocument();
    expect(within(controlPanel).getByTestId('historical-control-section-execute')).toBeInTheDocument();
    expect(within(controlPanel).getByTestId('historical-control-section-results')).toBeInTheDocument();
  });

  it('shows expanded deterministic controls in Professional Mode', async () => {
    renderBacktestRoutes();

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('tab', { name: '专业' }));

    expect(screen.getByRole('tab', { name: '专业' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByTestId('backtest-unified-shell')).toHaveAttribute('data-module', 'rule');
    expect(screen.getByTestId('backtest-control-panel-expanded')).toBeInTheDocument();
    expect(screen.queryByTestId('backtest-display-board')).not.toBeInTheDocument();
    expect(screen.getByTestId('backtest-control-section-symbol')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-control-section-setup')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-control-section-strategy')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-control-section-confirm')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-control-section-run')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-display-section-history')).toBeInTheDocument();
    expect(screen.queryByTestId('deterministic-backtest-chart-workspace')).not.toBeInTheDocument();
  });

  it('launches deterministic backtests into the dedicated result page flow', async () => {
    renderBacktestRoutes();

    await parseDeterministicStrategy();

    fireEvent.click(screen.getByLabelText(/我已确认当前解析结果与执行假设/i));
    fireEvent.click(within(screen.getByTestId('backtest-control-section-strategy')).getByRole('button', { name: '确认并打开结果页' }));

    expect(runRuleBacktest).toHaveBeenCalledTimes(1);
    expect(runRuleBacktest).toHaveBeenCalledWith(
      expect.objectContaining({
        code: 'ORCL',
        startDate: '2025-01-01',
        endDate: '2025-12-31',
        benchmarkMode: 'auto',
        waitForCompletion: false,
        confirmed: true,
      }),
    );

    expect(await screen.findByTestId('deterministic-backtest-result-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '确定性回测结果 #99' })).toBeInTheDocument();
    expect(await screen.findByTestId('deterministic-backtest-result-view')).toHaveAttribute('data-run-id', '99');
    expect(screen.getByTestId('deterministic-backtest-chart-workspace')).toBeInTheDocument();
    expect(screen.getByLabelText('累计收益率图')).toBeInTheDocument();
    expect(screen.getByLabelText('回测范围选择器')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '概览' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: '审计明细' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '交易记录' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '参数与假设' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '历史结果' })).toBeInTheDocument();
  }, 10000);

  it('opens deterministic history items in the dedicated result page route', async () => {
    const historySummary = makeRuleRunResponse({
      id: 123,
      runAt: '2026-04-08T08:00:00Z',
      completedAt: '2026-04-08T08:02:00Z',
      status: 'completed',
      statusMessage: '历史运行已完成。',
      auditRows: [
        {
          date: '2026-02-01',
          targetPosition: 0,
          totalPortfolioValue: 100000,
          cumulativeStrategyReturnPct: 0,
          dailyPnl: 0,
          dailyReturnPct: 0,
        },
        {
          date: '2026-02-02',
          targetPosition: 1,
          executedAction: 'buy',
          fillPrice: 99,
          totalPortfolioValue: 101500,
          cumulativeStrategyReturnPct: 1.5,
          dailyPnl: 1500,
          dailyReturnPct: 1.5,
        },
        {
          date: '2026-02-03',
          targetPosition: 0,
          executedAction: 'sell',
          fillPrice: 104,
          totalPortfolioValue: 104000,
          cumulativeStrategyReturnPct: 4,
          dailyPnl: 2500,
          dailyReturnPct: 2.46,
        },
      ],
    });

    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [historySummary],
    });
    getRuleBacktestRun.mockResolvedValue(historySummary);

    renderBacktestRoutes();

    await waitFor(() => expect(getRuleBacktestRuns).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: '查看' }));

    expect(await screen.findByTestId('deterministic-backtest-result-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '确定性回测结果 #123' })).toBeInTheDocument();
    expect(await screen.findByTestId('deterministic-backtest-result-view')).toHaveAttribute('data-run-id', '123');
    expect(screen.getByTestId('deterministic-backtest-chart-workspace')).toHaveAttribute('data-row-count', '3');
  }, 10000);

  it('applies saved presets on the configuration page', async () => {
    window.localStorage.setItem(RULE_BACKTEST_PRESET_STORAGE_KEY, JSON.stringify([
      {
        id: 'saved-1',
        kind: 'saved',
        name: 'ORCL Swing',
        savedAt: '2026-04-12T08:00:00Z',
        sourceRunId: 99,
        code: 'ORCL',
        strategyText: 'MACD金叉买入，死叉卖出',
        startDate: '2026-01-01',
        endDate: '2026-03-31',
        lookbackBars: '126',
        initialCapital: '150000',
        feeBps: '3',
        slippageBps: '2',
        benchmarkMode: 'etf_qqq',
        benchmarkCode: '',
      },
    ]));

    renderBacktestRoutes();

    expect(await screen.findByText('快速复用')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '应用' }));

    expect((screen.getByLabelText('股票代码') as HTMLInputElement).value).toBe('ORCL');
    expect((screen.getByLabelText('初始资金') as HTMLInputElement).value).toBe('150000');
  });
});
