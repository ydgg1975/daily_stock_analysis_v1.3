import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { RuleBacktestRunResponse } from '../../../types/backtest';
import { DeterministicAuditTable, DeterministicBacktestResultView } from '../DeterministicBacktestResultView';
import { normalizeDeterministicBacktestResult } from '../normalizeDeterministicBacktestResult';

function makeViewerRun(overrides: Partial<RuleBacktestRunResponse> = {}): RuleBacktestRunResponse {
  const auditRows = Array.from({ length: 70 }, (_, index) => {
    const day = String(index + 1).padStart(2, '0');
    return {
      date: `2026-03-${day}`,
      symbolClose: 100 + index,
      benchmarkClose: 98 + index * 0.8,
      signalSummary: index === 10 ? 'MA5 > MA20' : null,
      targetPosition: index >= 10 && index < 40 ? 1 : 0,
      executedAction: index === 10 ? 'buy' : index === 40 ? 'sell' : null,
      fillPrice: index === 10 ? 110 : index === 40 ? 140 : null,
      sharesHeld: index >= 10 && index < 40 ? 1000 : 0,
      cash: index >= 10 && index < 40 ? 5000 : 100000,
      holdingsValue: index >= 10 && index < 40 ? 100000 + index * 100 : 0,
      totalPortfolioValue: 100000 + index * 500,
      dailyPnl: index === 0 ? 0 : 500,
      dailyReturnPct: index === 0 ? 0 : 0.5,
      cumulativeStrategyReturnPct: index * 0.8,
      cumulativeBenchmarkReturnPct: index * 0.6,
      cumulativeBuyAndHoldReturnPct: index * 0.55,
      fees: 0,
      slippage: 0,
      notes: null,
      unavailableReason: null,
    };
  });

  return {
    id: 101,
    code: 'ORCL',
    strategyText: 'MA cross',
    parsedStrategy: {} as RuleBacktestRunResponse['parsedStrategy'],
    strategyHash: 'hash',
    timeframe: 'daily',
    startDate: '2026-03-01',
    endDate: '2026-05-09',
    periodStart: '2026-03-01',
    periodEnd: '2026-05-09',
    lookbackBars: 252,
    initialCapital: 100000,
    feeBps: 0,
    slippageBps: 0,
    parsedConfidence: 0.97,
    needsConfirmation: false,
    warnings: [],
    runAt: '2026-05-10T08:00:00Z',
    completedAt: '2026-05-10T08:03:00Z',
    status: 'completed',
    statusMessage: '规则回测已完成，可查看交易明细与执行假设。',
    statusHistory: [
      { status: 'queued', at: '2026-05-10T08:00:00Z' },
      { status: 'completed', at: '2026-05-10T08:03:00Z' },
    ],
    noResultReason: null,
    noResultMessage: null,
    tradeCount: 2,
    winCount: 1,
    lossCount: 1,
    totalReturnPct: 12.4,
    annualizedReturnPct: 18.1,
    benchmarkMode: 'auto',
    benchmarkCode: null,
    benchmarkReturnPct: 9.2,
    excessReturnVsBenchmarkPct: 3.2,
    buyAndHoldReturnPct: 8.5,
    excessReturnVsBuyAndHoldPct: 3.9,
    winRatePct: 50,
    avgTradeReturnPct: 6.2,
    maxDrawdownPct: 4.3,
    avgHoldingDays: 8,
    avgHoldingBars: 8,
    avgHoldingCalendarDays: 9,
    finalEquity: 112400,
    summary: {},
    executionAssumptions: {
      signalEvaluationTiming: 'bar close',
      entryFillTiming: 'next bar open',
    },
    benchmarkCurve: [],
    benchmarkSummary: {
      label: 'QQQ',
      requestedMode: 'auto',
      resolvedMode: 'etf_qqq',
      method: 'benchmark_security',
      returnPct: 9.2,
    },
    buyAndHoldCurve: [],
    buyAndHoldSummary: {
      label: '当前标的买入并持有',
      requestedMode: 'same_symbol_buy_and_hold',
      resolvedMode: 'same_symbol_buy_and_hold',
      method: 'same_symbol_buy_and_hold',
      returnPct: 8.5,
    },
    auditRows,
    dailyReturnSeries: [],
    exposureCurve: [],
    aiSummary: null,
    equityCurve: [],
    trades: [],
    ...overrides,
  };
}

describe('DeterministicBacktestResultView', () => {
  it('renders a non-empty KPI and chart-centered overview from normalized data', () => {
    render(<DeterministicBacktestResultView run={makeViewerRun()} />);

    const resultView = screen.getByTestId('deterministic-backtest-result-view');
    const dashboard = screen.getByTestId('deterministic-result-dashboard');
    const workspace = screen.getByTestId('deterministic-backtest-chart-workspace');
    const returnSvg = screen.getByLabelText('累计收益率图');

    expect(resultView).toHaveAttribute('data-row-count', '70');
    expect(resultView).toHaveAttribute('data-main-series-length', '70');
    expect(resultView).toHaveAttribute('data-daily-pnl-series-length', '70');
    expect(resultView).toHaveAttribute('data-position-series-length', '70');
    expect(resultView).toHaveAttribute('data-kpi-count', '6');
    expect(resultView).toHaveAttribute('data-density', 'dense');
    expect(dashboard).toBeInTheDocument();
    expect(screen.getByText('关键指标')).toBeInTheDocument();
    expect(screen.getByText('夏普')).toBeInTheDocument();
    expect(screen.queryByText('日级审计 / 对账')).not.toBeInTheDocument();
    expect(screen.queryByText('交易 / 事件日志')).not.toBeInTheDocument();
    expect(screen.queryByText('结果指标')).not.toBeInTheDocument();
    expect(screen.queryByText('联动结果图表')).not.toBeInTheDocument();
    expect(workspace).toHaveAttribute('data-row-count', '70');
    expect(workspace).toHaveAttribute('data-main-series-length', '70');
    expect(workspace).toHaveAttribute('data-daily-pnl-series-length', '70');
    expect(workspace).toHaveAttribute('data-position-series-length', '70');
    expect(workspace).toHaveAttribute('data-density', 'dense');
    expect(Number(workspace.getAttribute('data-main-panel-height'))).toBeGreaterThanOrEqual(200);
    expect(Number(workspace.getAttribute('data-main-panel-height'))).toBeLessThanOrEqual(220);
    expect(Number(workspace.getAttribute('data-daily-panel-height'))).toBeGreaterThanOrEqual(64);
    expect(Number(workspace.getAttribute('data-daily-panel-height'))).toBeLessThanOrEqual(72);
    expect(Number(workspace.getAttribute('data-position-panel-height'))).toBeGreaterThanOrEqual(48);
    expect(Number(workspace.getAttribute('data-position-panel-height'))).toBeLessThanOrEqual(56);
    expect(Number(workspace.getAttribute('data-brush-height'))).toBeGreaterThanOrEqual(32);
    expect(Number(workspace.getAttribute('data-brush-height'))).toBeLessThanOrEqual(36);
    expect(workspace).toHaveAttribute('data-tooltip-visible', 'false');
    expect(returnSvg.querySelector('.chart-card__line--strategy')?.getAttribute('points')).toBeTruthy();
  });

  it('applies one shared density level to KPI sizing and chart sizing together', () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: 1680 });
    window.dispatchEvent(new Event('resize'));

    render(<DeterministicBacktestResultView run={makeViewerRun()} />);

    const resultView = screen.getByTestId('deterministic-backtest-result-view');
    const workspace = screen.getByTestId('deterministic-backtest-chart-workspace');

    expect(resultView).toHaveAttribute('data-density', 'comfortable');
    expect(workspace).toHaveAttribute('data-density', 'comfortable');
    expect(workspace).toHaveAttribute('data-main-panel-height', '248');
    expect(workspace).toHaveAttribute('data-daily-panel-height', '88');
    expect(workspace).toHaveAttribute('data-position-panel-height', '72');
    expect(workspace).toHaveAttribute('data-brush-height', '44');

    Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: 1024 });
    window.dispatchEvent(new Event('resize'));
  });

  it('lets quick ranges, brush sliders, and hover all update the shared workspace state', () => {
    render(<DeterministicBacktestResultView run={makeViewerRun()} />);

    const workspace = screen.getByTestId('deterministic-backtest-chart-workspace');

    fireEvent.click(screen.getByRole('button', { name: '近1个月' }));
    expect(workspace).toHaveAttribute('data-visible-rows', '21');

    fireEvent.change(screen.getByLabelText('开始'), { target: { value: '20' } });
    fireEvent.change(screen.getByLabelText('结束'), { target: { value: '39' } });

    expect(workspace).toHaveAttribute('data-visible-start-index', '20');
    expect(workspace).toHaveAttribute('data-visible-end-index', '39');
    expect(workspace).toHaveAttribute('data-visible-rows', '20');

    const workspaceShell = workspace.querySelector('.backtest-unified-chart-viewer__workspace-shell') as HTMLElement;
    vi.spyOn(workspaceShell, 'getBoundingClientRect').mockReturnValue({
      x: 0,
      y: 0,
      width: 820,
      height: 460,
      top: 0,
      left: 0,
      right: 820,
      bottom: 460,
      toJSON: () => ({}),
    });

    const hoverSurface = screen.getByTestId('deterministic-chart-surface-return');
    vi.spyOn(hoverSurface, 'getBoundingClientRect').mockReturnValue({
      x: 0,
      y: 0,
      width: 400,
      height: 100,
      top: 0,
      left: 0,
      right: 400,
      bottom: 100,
      toJSON: () => ({}),
    });

    fireEvent.mouseMove(hoverSurface, { clientX: 120, clientY: 30 });

    expect(workspace.getAttribute('data-hovered-date')).toBe('2026-03-27');
    const hoverDetail = screen.getByTestId('deterministic-chart-hover-card');
    expect(workspace).toHaveAttribute('data-tooltip-visible', 'true');
    expect(hoverDetail).toHaveAttribute('data-visible', 'true');
    expect(within(hoverDetail).getByText('当日详情')).toBeInTheDocument();
    expect(within(hoverDetail).getAllByText('2026-03-27')).toHaveLength(2);
    const firstTooltipLeft = hoverDetail.getAttribute('data-tooltip-left');
    const firstTooltipTop = hoverDetail.getAttribute('data-tooltip-top');
    expect(Number(firstTooltipLeft)).toBeGreaterThanOrEqual(120);
    expect(Number(firstTooltipLeft)).toBeLessThanOrEqual(150);
    expect(Number(firstTooltipTop)).toBeGreaterThanOrEqual(36);
    expect(Number(firstTooltipTop)).toBeLessThanOrEqual(56);

    fireEvent.mouseMove(hoverSurface, { clientX: 300, clientY: 56 });

    const secondTooltipLeft = hoverDetail.getAttribute('data-tooltip-left');
    const secondTooltipTop = hoverDetail.getAttribute('data-tooltip-top');
    expect(secondTooltipLeft).not.toBe(firstTooltipLeft);
    expect(secondTooltipTop).not.toBe(firstTooltipTop);
    expect(Number(secondTooltipLeft)).toBeGreaterThanOrEqual(300);
    expect(Number(secondTooltipLeft)).toBeLessThanOrEqual(330);
    expect(Number(secondTooltipTop)).toBeGreaterThanOrEqual(62);
    expect(Number(secondTooltipTop)).toBeLessThanOrEqual(82);
  });

  it('exports csv from stored audit rows instead of recomputed viewer rows', async () => {
    const createObjectUrlMock = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test');
    const revokeObjectUrlMock = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    const clickMock = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const run = makeViewerRun({
      auditRows: [
        {
          date: '2026-03-01',
          symbolClose: 101,
          benchmarkClose: 99,
          position: 1,
          shares: 100,
          cash: 90000,
          holdingsValue: 10100,
          totalPortfolioValue: 100100,
          dailyPnl: 100,
          dailyReturn: 0.1,
          cumulativeReturn: 0.1,
          benchmarkCumulativeReturn: 0.05,
          buyHoldCumulativeReturn: 0.04,
          action: 'buy',
          fillPrice: 101,
          signalSummary: 'stored-row',
          notes: 'stored-note',
        },
      ],
      equityCurve: [
        { date: '2026-03-01', close: 888, totalPortfolioValue: 999999, cumulativeReturnPct: 88 },
      ],
    });
    const normalized = normalizeDeterministicBacktestResult(run);

    render(<DeterministicAuditTable run={run} rows={normalized.rows} />);

    fireEvent.click(screen.getByRole('button', { name: '导出 CSV' }));

    const blob = createObjectUrlMock.mock.calls[0]?.[0] as Blob;
    const content = await blob.text();
    expect(content).toContain('"101"');
    expect(content).toContain('"stored-note"');
    expect(content).not.toContain('"888"');

    createObjectUrlMock.mockRestore();
    revokeObjectUrlMock.mockRestore();
    clickMock.mockRestore();
  });
});
