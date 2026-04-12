import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { RuleBacktestRunResponse } from '../../types/backtest';
import DeterministicBacktestResultPage from '../DeterministicBacktestResultPage';

const {
  getRuleBacktestRun,
  getRuleBacktestRuns,
  getRuleBacktestRunStatus,
  cancelRuleBacktestRun,
} = vi.hoisted(() => ({
  getRuleBacktestRun: vi.fn(),
  getRuleBacktestRuns: vi.fn(),
  getRuleBacktestRunStatus: vi.fn(),
  cancelRuleBacktestRun: vi.fn(),
}));

vi.mock('../../api/backtest', () => ({
  backtestApi: {
    getRuleBacktestRun,
    getRuleBacktestRuns,
    getRuleBacktestRunStatus,
    cancelRuleBacktestRun,
  },
}));

function renderResultPage(initialEntries: string[] = ['/backtest/results/99']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/backtest/results/:runId" element={<DeterministicBacktestResultPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function makeResultRun(overrides: Partial<RuleBacktestRunResponse> = {}): RuleBacktestRunResponse {
  const auditRows = Array.from({ length: 3 }, (_, index) => ({
    date: `2026-03-0${index + 1}`,
    symbolClose: 100 + index,
    benchmarkClose: 98 + index,
    signalSummary: index === 1 ? 'MA5 > MA20' : null,
    targetPosition: index === 1 ? 1 : 0,
    executedAction: index === 1 ? 'buy' : index === 2 ? 'sell' : null,
    fillPrice: index === 1 ? 101 : index === 2 ? 104 : null,
    sharesHeld: index === 1 ? 1000 : 0,
    cash: index === 1 ? 5000 : 100000,
    holdingsValue: index === 1 ? 101000 : 0,
    totalPortfolioValue: index === 0 ? 100000 : index === 1 ? 101500 : 104000,
    dailyPnl: index === 0 ? 0 : index === 1 ? 1500 : 2500,
    dailyReturnPct: index === 0 ? 0 : index === 1 ? 1.5 : 2.46,
    cumulativeStrategyReturnPct: index === 0 ? 0 : index === 1 ? 1.5 : 4,
    cumulativeBenchmarkReturnPct: index === 0 ? 0 : index === 1 ? 1.2 : 2.8,
    cumulativeBuyAndHoldReturnPct: index === 0 ? 0 : index === 1 ? 1 : 2.6,
    fees: 0,
    slippage: 0,
    notes: null,
    unavailableReason: null,
  }));

  return {
    id: 99,
    code: 'ORCL',
    strategyText: 'MA cross',
    parsedStrategy: {
      version: 'v1',
      timeframe: 'daily',
      sourceText: 'MA cross',
      normalizedText: 'SMA5 上穿 SMA20 买入，下穿卖出。',
      entry: { type: 'group', op: 'and', rules: [] },
      exit: { type: 'group', op: 'or', rules: [] },
      confidence: 0.97,
      needsConfirmation: false,
      ambiguities: [],
      summary: {
        entry: 'SMA5 上穿 SMA20',
        exit: 'SMA5 下穿 SMA20',
        strategy: '均线交叉策略',
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
      coreIntentSummary: '已识别为均线交叉主规则。',
      interpretationConfidence: 0.97,
      supportedPortionSummary: '已识别为均线交叉主规则。',
      rewriteSuggestions: [],
      parseWarnings: [],
      setup: {
        symbol: 'ORCL',
        startDate: '2026-03-01',
        endDate: '2026-03-31',
        initialCapital: 100000,
      },
      strategySpec: {
        strategyType: 'moving_average_crossover',
        strategyFamily: 'moving_average_crossover',
        symbol: 'ORCL',
        timeframe: 'daily',
        dateRange: {
          startDate: '2026-03-01',
          endDate: '2026-03-31',
        },
        capital: {
          initialCapital: 100000,
          currency: 'USD',
        },
        signal: {
          indicatorFamily: 'moving_average',
          fastPeriod: 5,
          slowPeriod: 20,
          fastType: 'simple',
          slowType: 'simple',
          entryCondition: 'cross_above',
          exitCondition: 'cross_below',
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
        costs: {
          feeBps: 0,
          slippageBps: 0,
        },
      },
    } as RuleBacktestRunResponse['parsedStrategy'],
    strategyHash: 'hash',
    timeframe: 'daily',
    startDate: '2026-03-01',
    endDate: '2026-03-31',
    periodStart: '2026-03-01',
    periodEnd: '2026-03-31',
    lookbackBars: 252,
    initialCapital: 100000,
    feeBps: 0,
    slippageBps: 0,
    parsedConfidence: 0.97,
    needsConfirmation: false,
    warnings: [],
    runAt: '2026-04-07T08:00:00Z',
    completedAt: '2026-04-07T08:02:00Z',
    status: 'completed',
    statusMessage: '规则回测已完成。',
    statusHistory: [
      { status: 'queued', at: '2026-04-07T08:00:00Z' },
      { status: 'completed', at: '2026-04-07T08:02:00Z' },
    ],
    noResultReason: null,
    noResultMessage: null,
    tradeCount: 1,
    winCount: 1,
    lossCount: 0,
    totalReturnPct: 4,
    annualizedReturnPct: 6.1,
    benchmarkMode: 'auto',
    benchmarkCode: null,
    benchmarkReturnPct: 2.8,
    excessReturnVsBenchmarkPct: 1.2,
    buyAndHoldReturnPct: 2.6,
    excessReturnVsBuyAndHoldPct: 1.4,
    winRatePct: 100,
    avgTradeReturnPct: 4,
    maxDrawdownPct: 1.3,
    avgHoldingDays: 3,
    avgHoldingBars: 3,
    avgHoldingCalendarDays: 4,
    finalEquity: 104000,
    summary: {},
    executionAssumptions: {
      signalEvaluationTiming: 'bar close',
      entryFillTiming: 'next bar open',
      positionSizing: 'all_available_capital',
    },
    benchmarkCurve: [],
    benchmarkSummary: {
      label: 'QQQ',
      requestedMode: 'auto',
      resolvedMode: 'etf_qqq',
      method: 'benchmark_security',
      priceBasis: 'close',
      returnPct: 2.8,
    },
    buyAndHoldCurve: [],
    buyAndHoldSummary: {
      label: '当前标的买入并持有',
      requestedMode: 'same_symbol_buy_and_hold',
      resolvedMode: 'same_symbol_buy_and_hold',
      method: 'same_symbol_buy_and_hold',
      priceBasis: 'close',
      returnPct: 2.6,
    },
    auditRows,
    executionTrace: {
      source: 'storedExecutionTrace',
      rows: auditRows.map((row) => ({
        date: row.date,
        symbolClose: row.symbolClose,
        benchmarkClose: row.benchmarkClose,
        signalSummary: row.signalSummary,
        action: row.executedAction,
        actionDisplay: row.executedAction === 'buy' ? '买入' : row.executedAction === 'sell' ? '卖出' : '持有',
        fillPrice: row.fillPrice,
        shares: row.sharesHeld,
        cash: row.cash,
        holdingsValue: row.holdingsValue,
        totalPortfolioValue: row.totalPortfolioValue,
        dailyPnl: row.dailyPnl,
        dailyReturn: row.dailyReturnPct,
        cumulativeReturn: row.cumulativeStrategyReturnPct,
        benchmarkCumulativeReturn: row.cumulativeBenchmarkReturnPct,
        buyHoldCumulativeReturn: row.cumulativeBuyAndHoldReturnPct,
        position: row.targetPosition,
        fees: row.fees,
        slippage: row.slippage,
        notes: row.notes,
        unavailableReason: row.unavailableReason,
        assumptionsDefaults: 'next bar open / long only',
        fallback: '',
      })),
      assumptionsDefaults: {
        summaryText: 'next bar open / long only',
      },
      fallback: {
        runFallback: false,
        traceRebuilt: false,
        note: '标准执行路径',
      },
    },
    dailyReturnSeries: [],
    exposureCurve: [],
    aiSummary: null,
    equityCurve: [],
    trades: [],
    ...overrides,
  };
}

describe('DeterministicBacktestResultPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    vi.stubGlobal('confirm', vi.fn(() => true));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('polls processing runs on the result page and then renders the completed analysis workspace', async () => {
    const queuedRun = makeResultRun({
      status: 'queued',
      completedAt: null,
      statusMessage: '策略已提交，等待开始执行。',
      statusHistory: [{ status: 'queued', at: '2026-04-07T08:00:00Z' }],
      auditRows: [],
    });
    const completedRun = makeResultRun();

    getRuleBacktestRun
      .mockResolvedValueOnce(queuedRun)
      .mockResolvedValueOnce(completedRun);
    getRuleBacktestRunStatus.mockResolvedValueOnce({
      id: 99,
      code: 'ORCL',
      status: 'completed',
      statusMessage: '规则回测已完成。',
      statusHistory: [
        { status: 'queued', at: '2026-04-07T08:00:00Z' },
        { status: 'completed', at: '2026-04-07T08:02:00Z' },
      ],
      runAt: '2026-04-07T08:00:00Z',
      completedAt: '2026-04-07T08:02:00Z',
      noResultReason: null,
      noResultMessage: null,
      tradeCount: 1,
      parsedConfidence: 0.97,
      needsConfirmation: false,
    });
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [completedRun],
    });

    vi.useFakeTimers();
    renderResultPage();

    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText('页面正在自动跟踪状态')).toBeInTheDocument();
    expect(screen.queryByTestId('deterministic-backtest-result-view')).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1800);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByTestId('deterministic-backtest-result-view')).toHaveAttribute('data-run-id', '99');
    expect(screen.getByTestId('deterministic-backtest-chart-workspace')).toHaveAttribute('data-row-count', '3');
    expect(screen.getByRole('tab', { name: '概览' })).toHaveAttribute('aria-selected', 'true');
    expect(getRuleBacktestRunStatus).toHaveBeenCalledTimes(1);
    expect(getRuleBacktestRun).toHaveBeenCalledTimes(2);
  }, 10000);

  it('keeps the first screen compact and moves deep data into dedicated tabs', async () => {
    const currentRun = makeResultRun({ id: 99, runAt: '2026-04-07T08:00:00Z' });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toHaveAttribute('data-run-id', '99');
    expect(screen.getByTestId('deterministic-backtest-result-page')).toHaveAttribute('data-density', 'dense');
    expect(screen.getByTestId('deterministic-result-page-hero')).toBeInTheDocument();
    expect(screen.getByTestId('deterministic-result-dashboard')).toBeInTheDocument();
    expect(screen.queryByText('结果指标')).not.toBeInTheDocument();
    expect(screen.queryByText('联动结果图表')).not.toBeInTheDocument();
    expect(screen.getByTestId('deterministic-backtest-chart-workspace')).toHaveAttribute('data-row-count', '3');
    expect(screen.getByRole('tab', { name: '概览' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.queryByText('日级审计 / 对账')).not.toBeInTheDocument();
    expect(screen.queryByText('交易 / 事件日志')).not.toBeInTheDocument();
    expect(screen.queryByText('同标的历史回测')).not.toBeInTheDocument();
    expect(screen.queryByText('参数快照')).not.toBeInTheDocument();
    expect(screen.getByText('回测已完成')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '审计明细' }));
    expect(await screen.findByTestId('deterministic-result-tab-panel-audit')).toBeInTheDocument();
    expect(screen.getByText('日级审计 / 对账')).toBeInTheDocument();
    expect(screen.getByText('执行轨迹')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '关键节点' })).toHaveAttribute('aria-selected', 'true');

    fireEvent.click(screen.getByRole('tab', { name: '交易记录' }));
    expect(await screen.findByTestId('deterministic-result-tab-panel-trades')).toBeInTheDocument();
    expect(screen.getByText('交易 / 事件日志')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '参数与假设' }));
    expect(await screen.findByTestId('deterministic-result-tab-panel-parameters')).toBeInTheDocument();
    expect(screen.getByText('参数快照')).toBeInTheDocument();
    expect(screen.getAllByText('实际执行内容').length).toBeGreaterThan(0);
    expect(screen.getByText('原始输入与解析')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '历史结果' }));
    expect(await screen.findByTestId('deterministic-result-tab-panel-history')).toBeInTheDocument();
    expect(screen.getByText('同标的历史回测')).toBeInTheDocument();
  }, 10000);

  it('aligns result-page strategy wording with the confirmation-page canonical spec language', async () => {
    const currentRun = makeResultRun();

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '参数与假设' }));
    expect(await screen.findByTestId('deterministic-result-tab-panel-parameters')).toBeInTheDocument();

    expect(screen.getAllByText('策略族 · 均线交叉').length).toBeGreaterThan(0);
    expect(screen.getByText('规格来源 · 显式 strategy_spec')).toBeInTheDocument();
    expect(screen.getByText('归一化 · 已完成归一化')).toBeInTheDocument();
    expect(screen.getAllByText('SMA5 上穿 SMA20').length).toBeGreaterThan(0);
    expect(screen.getAllByText('收盘后判定').length).toBeGreaterThan(0);
    expect(screen.getAllByText('下一根开盘成交').length).toBeGreaterThan(0);

    expect(screen.getAllByText('策略族').length).toBeGreaterThan(0);
    expect(screen.getAllByText('均线交叉').length).toBeGreaterThan(0);
    expect(screen.getAllByText('已完成归一化').length).toBeGreaterThan(0);
  });

  it('lets users cancel active runs from the result page', async () => {
    const queuedRun = makeResultRun({
      status: 'queued',
      completedAt: null,
      statusMessage: '策略已提交，等待开始执行。',
      statusHistory: [{ status: 'queued', at: '2026-04-07T08:00:00Z' }],
      auditRows: [],
      executionTrace: null,
    });
    const cancelledRun = makeResultRun({
      status: 'cancelled',
      completedAt: '2026-04-07T08:00:45Z',
      statusMessage: '规则回测已取消。',
      statusHistory: [
        { status: 'queued', at: '2026-04-07T08:00:00Z' },
        { status: 'cancelled', at: '2026-04-07T08:00:45Z' },
      ],
      auditRows: [],
      executionTrace: null,
    });

    getRuleBacktestRun
      .mockResolvedValueOnce(queuedRun)
      .mockResolvedValueOnce(cancelledRun);
    cancelRuleBacktestRun.mockResolvedValue({
      id: 99,
      code: 'ORCL',
      status: 'cancelled',
      statusMessage: '规则回测已取消。',
      statusHistory: cancelledRun.statusHistory,
      runAt: queuedRun.runAt,
      completedAt: cancelledRun.completedAt,
      noResultReason: 'cancelled',
      noResultMessage: '规则回测已取消。',
      tradeCount: 0,
      parsedConfidence: 0.97,
      needsConfirmation: false,
    });
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [cancelledRun],
    });

    renderResultPage();

    expect(await screen.findByText('取消运行')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '取消运行' }));

    await waitFor(() => {
      expect(cancelRuleBacktestRun).toHaveBeenCalledWith(99);
    });
    expect(await screen.findByText('回测已取消')).toBeInTheDocument();
  });

  it('keeps historical navigation on the same result-page rendering path', async () => {
    const currentRun = makeResultRun({ id: 99, runAt: '2026-04-07T08:00:00Z' });
    const historyRun = makeResultRun({
      id: 123,
      runAt: '2026-04-08T08:00:00Z',
      completedAt: '2026-04-08T08:02:00Z',
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

    getRuleBacktestRun.mockImplementation(async (id: number) => (id === 123 ? historyRun : currentRun));
    getRuleBacktestRuns.mockResolvedValue({
      total: 2,
      page: 1,
      limit: 10,
      items: [currentRun, historyRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toHaveAttribute('data-run-id', '99');
    fireEvent.click(screen.getByRole('tab', { name: '历史结果' }));
    expect(await screen.findByText('同标的历史回测')).toBeInTheDocument();
    const historyButtons = await screen.findAllByRole('button', { name: '查看' });

    fireEvent.click(historyButtons[1]);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: '确定性回测结果 #123' })).toBeInTheDocument();
    });
    expect(screen.getByTestId('deterministic-backtest-result-view')).toHaveAttribute('data-run-id', '123');
    expect(screen.getByTestId('deterministic-backtest-chart-workspace')).toHaveAttribute('data-row-count', '3');
  }, 10000);
});
