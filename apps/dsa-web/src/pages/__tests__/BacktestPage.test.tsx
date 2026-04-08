import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  BacktestRunHistoryItem,
  BacktestRunResponse,
  PrepareBacktestSamplesResponse,
  RuleBacktestParseResponse,
  RuleBacktestRunResponse,
} from '../../types/backtest';
import BacktestPage from '../BacktestPage';

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
}));

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
  },
}));

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
    executionAssumptions: {
      moduleType: 'historical_analysis_evaluation',
    },
  };
}

function makeRuleParseResponse(): RuleBacktestParseResponse {
  return {
    code: 'ORCL',
    strategyText: 'Buy when MA5 > MA20 and RSI6 < 40. Sell when MA5 < MA20 or RSI6 > 70.',
    parsedStrategy: {
      version: 'v1',
      timeframe: 'daily',
      sourceText: 'Buy when MA5 > MA20 and RSI6 < 40. Sell when MA5 < MA20 or RSI6 > 70.',
      normalizedText: 'BUY WHEN MA5 > MA20 AND RSI6 < 40; EXIT WHEN MA5 < MA20 OR RSI6 > 70',
      entry: {
        type: 'group',
        op: 'and',
        rules: [],
      },
      exit: {
        type: 'group',
        op: 'or',
        rules: [],
      },
      confidence: 0.97,
      needsConfirmation: false,
      ambiguities: [],
      summary: {
        entry: '买入条件：MA5 > MA20 且 RSI6 < 40',
        exit: '卖出条件：MA5 < MA20 或 RSI6 > 70',
      },
      maxLookback: 20,
    },
    confidence: 0.97,
    needsConfirmation: false,
    ambiguities: [],
    summary: {
      entry: '买入条件：MA5 > MA20 且 RSI6 < 40',
      exit: '卖出条件：MA5 < MA20 或 RSI6 > 70',
    },
    maxLookback: 20,
  };
}

function makeRuleRunResponse(overrides: Partial<RuleBacktestRunResponse> = {}): RuleBacktestRunResponse {
  return {
    id: 99,
    code: 'ORCL',
    strategyText: 'Buy when MA5 > MA20 and RSI6 < 40. Sell when MA5 < MA20 or RSI6 > 70.',
    parsedStrategy: makeRuleParseResponse().parsedStrategy,
    strategyHash: 'hash',
    timeframe: 'daily',
    lookbackBars: 252,
    initialCapital: 100000,
    feeBps: 0,
    slippageBps: 0,
    parsedConfidence: 0.97,
    needsConfirmation: false,
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
    },
    aiSummary: null,
    equityCurve: [],
    trades: [],
    ...overrides,
  };
}

describe('BacktestPage', () => {
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
      evalWindowDays: 10,
      minAgeDays: 14,
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
          { date: '2026-03-18', equity: 108500, cumulativeReturnPct: 8.5, drawdownPct: 0 },
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
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders the two backtest modules with explicit unit copy', async () => {
    render(<BacktestPage />);

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    expect(screen.getByRole('tab', { name: /Historical Analysis Evaluation/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Deterministic Rule Strategy Backtest/i })).toBeInTheDocument();
    expect(screen.getByText(/单位是 trading bars/i)).toBeInTheDocument();
    expect(screen.getByText(/单位是 calendar days/i)).toBeInTheDocument();
    expect(screen.getByText(/表示要准备多少条 analysis samples/i)).toBeInTheDocument();
  });

  it('submits historical evaluation with explicit maturity days instead of tying it to force rerun', async () => {
    render(<BacktestPage />);

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText('股票代码'), { target: { value: 'ORCL' } });
    fireEvent.change(screen.getByLabelText('评估窗口'), { target: { value: '15' } });
    fireEvent.change(screen.getByLabelText('成熟期'), { target: { value: '30' } });
    fireEvent.click(screen.getByLabelText(/覆盖已有同窗口结果/i));
    fireEvent.click(screen.getByRole('button', { name: '运行历史评估' }));

    await waitFor(() => expect(runBacktest).toHaveBeenCalledTimes(1));
    expect(runBacktest).toHaveBeenCalledWith(
      expect.objectContaining({
        code: 'ORCL',
        force: true,
        evalWindowDays: 15,
        minAgeDays: 30,
      }),
    );
  });

  it('submits deterministic rule backtests asynchronously and polls until completion', async () => {
    render(<BacktestPage />);

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('tab', { name: /Deterministic Rule Strategy Backtest/i }));
    fireEvent.change(screen.getByLabelText('股票代码'), { target: { value: 'ORCL' } });
    fireEvent.click(screen.getByRole('button', { name: '解析规则' }));

    expect(await screen.findByText('归一化策略预览')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/我已确认规则解析结果/i));
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('button', { name: '提交规则回测' }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(runRuleBacktest).toHaveBeenCalledTimes(1);
    expect(runRuleBacktest).toHaveBeenCalledWith(
      expect.objectContaining({
        code: 'ORCL',
        waitForCompletion: false,
        confirmed: true,
      }),
    );

    expect(screen.getByText('规则任务状态')).toBeInTheDocument();
    expect(screen.getByText('排队中')).toBeInTheDocument();

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(getRuleBacktestRun).toHaveBeenCalledTimes(1);
    expect(screen.getByText('规则回测已完成，可查看交易明细与执行假设。')).toBeInTheDocument();
    expect(screen.getByText('该策略相对 buy-and-hold 取得了正向超额收益，但交易样本仍然较少。')).toBeInTheDocument();
    expect(screen.getByText('交易明细')).toBeInTheDocument();
    expect(screen.getByText('MA5 > MA20')).toBeInTheDocument();
  }, 10000);
});
