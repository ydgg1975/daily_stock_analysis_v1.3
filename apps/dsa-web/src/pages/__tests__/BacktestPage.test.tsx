import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  BacktestResultItem,
  BacktestRunHistoryItem,
  BacktestRunResponse,
  PerformanceMetrics,
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

function makeResult(code = 'ORCL'): BacktestResultItem {
  return {
    analysisHistoryId: 101,
    code,
    analysisDate: '2026-03-18',
    evalWindowDays: 10,
    engineVersion: 'v1',
    evalStatus: 'completed',
    evaluatedAt: '2026-03-19T08:00:00Z',
    operationAdvice: '继续观察',
    positionRecommendation: 'hold',
    startPrice: 100,
    endClose: 106,
    maxHigh: 108,
    minLow: 98,
    stockReturnPct: 6,
    directionExpected: 'up',
    directionCorrect: true,
    outcome: 'win',
    stopLoss: 95,
    takeProfit: 110,
    hitStopLoss: false,
    hitTakeProfit: true,
    firstHit: 'take_profit',
    firstHitDate: '2026-03-20',
    firstHitTradingDays: 2,
    simulatedEntryPrice: 100,
    simulatedExitPrice: 110,
    simulatedExitReason: 'take_profit',
    simulatedReturnPct: 10,
  };
}

function makePerformance(scope: string, code?: string): PerformanceMetrics {
  return {
    scope,
    code,
    evalWindowDays: 10,
    engineVersion: 'v1',
    computedAt: '2026-03-19T08:00:00Z',
    totalEvaluations: 1,
    completedCount: 1,
    insufficientCount: 0,
    longCount: 1,
    cashCount: 0,
    winCount: 1,
    lossCount: 0,
    neutralCount: 0,
    directionAccuracyPct: 100,
    winRatePct: 100,
    neutralRatePct: 0,
    avgStockReturnPct: 6,
    avgSimulatedReturnPct: 10,
    stopLossTriggerRate: 0,
    takeProfitTriggerRate: 100,
    ambiguousRate: 0,
    avgDaysToFirstHit: 2,
    adviceBreakdown: {},
    diagnostics: {},
  };
}

function makeHistoryItem(id = 1, code = 'ORCL'): BacktestRunHistoryItem {
  return {
    id,
    code,
    evalWindowDays: 10,
    minAgeDays: 14,
    force: false,
    runAt: '2026-03-19T08:00:00Z',
    completedAt: '2026-03-19T08:00:00Z',
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
      normalizedText: 'Buy when MA5 > MA20 and RSI6 < 40. Sell when MA5 < MA20 or RSI6 > 70.',
      entry: {
        type: 'group',
        op: 'and',
        rules: [
          {
            type: 'comparison',
            left: { kind: 'indicator', indicator: 'ma', period: 5 },
            compare: '>',
            right: { kind: 'indicator', indicator: 'ma', period: 20 },
            text: 'MA5 > MA20',
          },
          {
            type: 'comparison',
            left: { kind: 'indicator', indicator: 'rsi', period: 6 },
            compare: '<',
            right: { kind: 'value', value: 40 },
            text: 'RSI6 < 40',
          },
        ],
      },
      exit: {
        type: 'group',
        op: 'or',
        rules: [
          {
            type: 'comparison',
            left: { kind: 'indicator', indicator: 'ma', period: 5 },
            compare: '<',
            right: { kind: 'indicator', indicator: 'ma', period: 20 },
            text: 'MA5 < MA20',
          },
          {
            type: 'comparison',
            left: { kind: 'indicator', indicator: 'rsi', period: 6 },
            compare: '>',
            right: { kind: 'value', value: 70 },
            text: 'RSI6 > 70',
          },
        ],
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

function makeRuleRunResponse(): RuleBacktestRunResponse {
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
    parsedConfidence: 0.97,
    needsConfirmation: false,
    warnings: [],
    runAt: '2026-03-19T08:00:00Z',
    completedAt: '2026-03-19T08:00:00Z',
    status: 'completed',
    noResultReason: null,
    noResultMessage: null,
    tradeCount: 2,
    winCount: 1,
    lossCount: 1,
    totalReturnPct: 8.5,
    winRatePct: 50,
    avgTradeReturnPct: 4.25,
    maxDrawdownPct: 3.2,
    avgHoldingDays: 6,
    finalEquity: 108500,
    summary: {
      metrics: {
        totalReturnPct: 8.5,
      },
      parsedStrategySummary: makeRuleParseResponse().summary,
    },
    aiSummary: '该策略以均线趋势确认和 RSI 超卖过滤为核心，样本中有 2 笔交易，整体收益为正，但胜率一般。',
    equityCurve: [
      { date: '2026-03-01', equity: 100000, cumulativeReturnPct: 0, drawdownPct: 0 },
      { date: '2026-03-10', equity: 103000, cumulativeReturnPct: 3, drawdownPct: 0 },
      { date: '2026-03-18', equity: 108500, cumulativeReturnPct: 8.5, drawdownPct: 0 },
    ],
    trades: [
      {
        code: 'ORCL',
        entryDate: '2026-03-03',
        exitDate: '2026-03-07',
        entryPrice: 100,
        exitPrice: 106,
        entrySignal: '买入条件：MA5 > MA20 且 RSI6 < 40',
        exitSignal: '卖出条件：MA5 < MA20 或 RSI6 > 70',
        returnPct: 6,
        holdingDays: 5,
        entryRule: makeRuleParseResponse().parsedStrategy.entry,
        exitRule: makeRuleParseResponse().parsedStrategy.exit,
      },
      {
        code: 'ORCL',
        entryDate: '2026-03-11',
        exitDate: '2026-03-16',
        entryPrice: 107,
        exitPrice: 110,
        entrySignal: '买入条件：MA5 > MA20 且 RSI6 < 40',
        exitSignal: '卖出条件：MA5 < MA20 或 RSI6 > 70',
        returnPct: 2.8,
        holdingDays: 6,
        entryRule: makeRuleParseResponse().parsedStrategy.entry,
        exitRule: makeRuleParseResponse().parsedStrategy.exit,
      },
    ],
  };
}

describe('BacktestPage post-run loading', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    getResults.mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    getHistory.mockResolvedValue({
      total: 0,
      page: 1,
      limit: 10,
      items: [],
    });
    getSampleStatus.mockResolvedValue({
      code: 'ORCL',
      preparedCount: 0,
      preparedStartDate: null,
      preparedEndDate: null,
      latestPreparedAt: null,
      evalWindowDays: 10,
      minAgeDays: 14,
    });
    clearSamples.mockResolvedValue({
      code: 'ORCL',
      deletedRuns: 0,
      deletedResults: 0,
      deletedSamples: 0,
      deletedSummaries: 0,
      message: '回测样本已清理',
    });
    clearResults.mockResolvedValue({
      code: 'ORCL',
      deletedRuns: 0,
      deletedResults: 0,
      deletedSamples: 0,
      deletedSummaries: 0,
      message: '回测结果已清理',
    });
    getOverallPerformance.mockResolvedValue(null);
    getStockPerformance.mockResolvedValue(null);
    parseRuleStrategy.mockResolvedValue(makeRuleParseResponse());
    runRuleBacktest.mockResolvedValue(makeRuleRunResponse());
    getRuleBacktestRuns.mockResolvedValue({
      total: 0,
      page: 1,
      limit: 10,
      items: [],
    });
    getRuleBacktestRun.mockResolvedValue(makeRuleRunResponse());
    prepareSamples.mockResolvedValue({
      code: 'ORCL',
      sampleCount: 20,
      prepared: 0,
      skippedExisting: 0,
      marketRowsSaved: 0,
      candidateRows: 0,
      evalWindowDays: 10,
      minAgeDays: 14,
      noResultReason: null,
      noResultMessage: null,
      preparedStartDate: null,
      preparedEndDate: null,
      latestPreparedAt: null,
    } satisfies PrepareBacktestSamplesResponse);
    runBacktest.mockResolvedValue({
      runId: 1,
      runAt: '2026-03-19T08:00:00Z',
      processed: 1,
      saved: 1,
      completed: 1,
      insufficient: 0,
      errors: 0,
    } satisfies BacktestRunResponse);
  });

  it('renders the new result set after run even when performance summaries are missing', async () => {
    getResults
      .mockResolvedValueOnce({
        total: 0,
        page: 1,
        limit: 20,
        items: [],
      })
      .mockResolvedValueOnce({
        total: 1,
        page: 1,
        limit: 20,
        items: [makeResult('ORCL')],
      });
    getHistory.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [makeHistoryItem(1, 'ORCL')],
    });
    getSampleStatus.mockResolvedValue({
      code: 'ORCL',
      preparedCount: 8,
      preparedStartDate: '2026-03-01',
      preparedEndDate: '2026-03-18',
      latestPreparedAt: '2026-03-19T08:00:00Z',
      evalWindowDays: 10,
      minAgeDays: 14,
    });
    getOverallPerformance
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(null);
    getStockPerformance.mockResolvedValueOnce(null);
    runBacktest.mockResolvedValueOnce({
      runId: 1,
      runAt: '2026-03-19T08:00:00Z',
      processed: 0,
      saved: 0,
      completed: 0,
      insufficient: 0,
      errors: 0,
      candidateCount: 0,
      noResultReason: 'insufficient_historical_data',
      noResultMessage: '当前没有满足 14 天成熟窗口的分析记录，因此本次回测未生成结果。',
    } satisfies BacktestRunResponse);

    render(<BacktestPage />);

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByPlaceholderText('按股票代码筛选，留空则查看全部'), {
      target: { value: 'ORCL' },
    });
    fireEvent.click(screen.getByRole('button', { name: '运行回测' }));

    await waitFor(() => expect(runBacktest).toHaveBeenCalledTimes(1));
    expect(await screen.findAllByText('当前没有满足 14 天成熟窗口的分析记录，因此本次回测未生成结果。', { selector: 'p' })).toHaveLength(1);
    expect(screen.getByText('表现汇总尚未生成')).toBeInTheDocument();
    expect(screen.getByText(/暂无整体回测表现汇总/)).toBeInTheDocument();
    expect(screen.getByText(/暂无 ORCL 的单股表现汇总/)).toBeInTheDocument();
    expect(screen.getByText('继续观察')).toBeInTheDocument();
    expect(screen.getByText('样本状态')).toBeInTheDocument();
    expect(screen.getByText('回测历史')).toBeInTheDocument();
  });

  it('parses a rule strategy, confirms it, and renders deterministic trade results', async () => {
    render(<BacktestPage />);

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByPlaceholderText('按股票代码筛选，留空则查看全部'), {
      target: { value: 'ORCL' },
    });
    const strategyBox = screen.getByPlaceholderText(/Buy when MA5 > MA20/i);
    fireEvent.change(strategyBox, {
      target: { value: 'Buy when MA5 > MA20 and RSI6 < 40. Sell when MA5 < MA20 or RSI6 > 70.' },
    });
    fireEvent.click(screen.getByRole('button', { name: '解析策略' }));

    expect(await screen.findByLabelText('我已确认解析结果，允许执行规则回测')).toBeInTheDocument();
    expect(parseRuleStrategy).toHaveBeenCalledWith(
      expect.objectContaining({
        code: 'ORCL',
        strategyText: expect.stringContaining('MA5 > MA20'),
      }),
    );

    fireEvent.click(screen.getByLabelText('我已确认解析结果，允许执行规则回测'));
    fireEvent.click(screen.getByRole('button', { name: '确认并运行' }));

    expect(await screen.findByText('规则回测结果')).toBeInTheDocument();
    expect(screen.getByText('AI 结果总结')).toBeInTheDocument();
    expect(screen.getByText('交易明细')).toBeInTheDocument();
    expect(screen.getByText('2026-03-03')).toBeInTheDocument();
    expect(screen.getByText('2026-03-11')).toBeInTheDocument();
    expect(runRuleBacktest).toHaveBeenCalledWith(
      expect.objectContaining({
        code: 'ORCL',
        confirmed: true,
        parsedStrategy: expect.objectContaining({ timeframe: 'daily' }),
      }),
    );
  });

  it('keeps rendered results visible when stock performance lookup fails with a non-404 error', async () => {
    getResults
      .mockResolvedValueOnce({
        total: 0,
        page: 1,
        limit: 20,
        items: [],
      })
      .mockResolvedValueOnce({
        total: 1,
        page: 1,
        limit: 20,
        items: [makeResult('ORCL')],
      });
    getHistory.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [makeHistoryItem(1, 'ORCL')],
    });
    getSampleStatus.mockResolvedValue({
      code: 'ORCL',
      preparedCount: 8,
      preparedStartDate: '2026-03-01',
      preparedEndDate: '2026-03-18',
      latestPreparedAt: '2026-03-19T08:00:00Z',
      evalWindowDays: 10,
      minAgeDays: 14,
    });
    getOverallPerformance
      .mockResolvedValueOnce(makePerformance('overall'))
      .mockResolvedValueOnce(makePerformance('overall'));
    getStockPerformance.mockRejectedValueOnce(new Error('detail fetch failed'));

    render(<BacktestPage />);

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByPlaceholderText('按股票代码筛选，留空则查看全部'), {
      target: { value: 'ORCL' },
    });
    fireEvent.click(screen.getByRole('button', { name: '运行回测' }));

    await waitFor(() => expect(getStockPerformance).toHaveBeenCalled());
    expect(screen.getByText('整体表现')).toBeInTheDocument();
    expect(screen.getAllByText('表现数据加载失败', { selector: 'p' })).toHaveLength(1);
    expect(getStockPerformance).toHaveBeenCalledWith('ORCL', 10);
  });

  it('shows a prepare samples action when history is insufficient and calls the warmup endpoint', async () => {
    getResults
      .mockResolvedValueOnce({
        total: 0,
        page: 1,
        limit: 20,
        items: [],
      })
      .mockResolvedValueOnce({
        total: 1,
        page: 1,
        limit: 20,
        items: [makeResult('ORCL')],
      });
    getHistory.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [makeHistoryItem(1, 'ORCL')],
    });
    getSampleStatus.mockResolvedValue({
      code: 'ORCL',
      preparedCount: 8,
      preparedStartDate: '2026-03-01',
      preparedEndDate: '2026-03-18',
      latestPreparedAt: '2026-03-19T08:00:00Z',
      evalWindowDays: 10,
      minAgeDays: 14,
    });
    getOverallPerformance.mockResolvedValueOnce(null);
    getStockPerformance.mockResolvedValueOnce(null);
    runBacktest.mockResolvedValueOnce({
      runId: 1,
      runAt: '2026-03-19T08:00:00Z',
      processed: 0,
      saved: 0,
      completed: 0,
      insufficient: 0,
      errors: 0,
      candidateCount: 0,
      noResultReason: 'insufficient_historical_data',
      noResultMessage: '当前没有满足 14 天成熟窗口的分析记录，因此本次回测未生成结果。',
    } satisfies BacktestRunResponse);
    prepareSamples.mockResolvedValueOnce({
      code: 'ORCL',
      sampleCount: 60,
      prepared: 8,
      skippedExisting: 0,
      marketRowsSaved: 0,
      candidateRows: 8,
      evalWindowDays: 10,
      minAgeDays: 14,
      noResultReason: null,
      noResultMessage: '已准备 8 条回测样本，可重新运行回测。',
      preparedStartDate: '2026-03-01',
      preparedEndDate: '2026-03-18',
      latestPreparedAt: '2026-03-19T08:00:00Z',
    });

    render(<BacktestPage />);

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByPlaceholderText('按股票代码筛选，留空则查看全部'), {
      target: { value: 'ORCL' },
    });
    fireEvent.click(screen.getByRole('button', { name: '运行回测' }));

    expect(await screen.findByText('需要准备回测样本')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '准备回测样本' })).not.toBeDisabled();
    });

    fireEvent.change(screen.getByRole('combobox'), {
      target: { value: '252' },
    });

    fireEvent.click(screen.getByRole('button', { name: '准备回测样本' }));

    await waitFor(() => {
      expect(prepareSamples).toHaveBeenCalledWith({
        code: 'ORCL',
        sampleCount: 252,
        evalWindowDays: undefined,
        forceRefresh: false,
      });
    });

    expect(await screen.findByText('回测样本已准备')).toBeInTheDocument();
    expect(screen.getByText(/已生成 8 条样本/)).toBeInTheDocument();
  });

  it('reopens a previous history run and clears sample/result state separately', async () => {
    getHistory.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [makeHistoryItem(7, 'ORCL')],
    });
    getSampleStatus.mockResolvedValue({
      code: 'ORCL',
      preparedCount: 12,
      preparedStartDate: '2026-03-01',
      preparedEndDate: '2026-03-18',
      latestPreparedAt: '2026-03-19T08:00:00Z',
      evalWindowDays: 10,
      minAgeDays: 14,
    });
    getResults
      .mockResolvedValueOnce({
        total: 1,
        page: 1,
        limit: 20,
        items: [makeResult('ORCL')],
      })
      .mockResolvedValueOnce({
        total: 1,
        page: 1,
        limit: 20,
        items: [makeResult('ORCL')],
      });

    render(<BacktestPage />);

    await waitFor(() => expect(getHistory).toHaveBeenCalled());

    expect(await screen.findByText('回测历史')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '查看' }));

    await waitFor(() => {
      expect(getResults).toHaveBeenCalledWith(expect.objectContaining({ runId: 7 }));
    });
  });

  it('exposes separate clear controls for samples and results', async () => {
    getHistory.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [makeHistoryItem(7, 'ORCL')],
    });
    getSampleStatus.mockResolvedValue({
      code: 'ORCL',
      preparedCount: 12,
      preparedStartDate: '2026-03-01',
      preparedEndDate: '2026-03-18',
      latestPreparedAt: '2026-03-19T08:00:00Z',
      evalWindowDays: 10,
      minAgeDays: 14,
    });

    render(<BacktestPage />);

    fireEvent.change(screen.getByPlaceholderText('按股票代码筛选，留空则查看全部'), {
      target: { value: 'ORCL' },
    });

    await waitFor(() => expect(screen.getByRole('button', { name: '清空样本' })).not.toBeDisabled());

    fireEvent.click(screen.getByRole('button', { name: '清空样本' }));

    await waitFor(() => {
      expect(clearSamples).toHaveBeenCalledWith('ORCL');
    });

    fireEvent.click(screen.getByRole('button', { name: '清空当前结果' }));

    await waitFor(() => {
      expect(clearResults).toHaveBeenCalledWith('ORCL');
    });
  });
});
