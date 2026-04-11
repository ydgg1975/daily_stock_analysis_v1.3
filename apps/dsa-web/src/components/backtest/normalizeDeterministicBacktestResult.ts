import type {
  RuleBacktestAuditRowItem,
  RuleBacktestBenchmarkSummary,
  RuleBacktestRunResponse,
  RuleBacktestTradeItem,
} from '../../types/backtest';

export type DeterministicBacktestNormalizedRow = {
  date: string;
  strategyCumReturn: number | null;
  benchmarkCumReturn: number | null;
  buyHoldCumReturn: number | null;
  dailyPnl: number | null;
  dailyReturn: number | null;
  position: number | null;
  action: string | null;
  fillPrice: number | null;
  shares: number | null;
  cash: number | null;
  totalValue: number | null;
  holdingsValue: number | null;
  symbolClose: number | null;
  benchmarkClose: number | null;
  signalSummary: string | null;
  notes: string | null;
  fees: number | null;
  slippage: number | null;
  drawdownPct: number | null;
  positionState: string | null;
  unavailableReason: string | null;
};

export type DeterministicBacktestTradeEvent = {
  key: string;
  date: string;
  action: string;
  fillPrice: number | null;
  shares: number | null;
  cash: number | null;
  totalValue: number | null;
  signalDate: string | null;
  signalSummary: string | null;
  trigger: string | null;
  returnPct: number | null;
  holdingBars: number | null;
  notes: string | null;
  source: 'row' | 'trade';
  tradeIndex: number | null;
};

export type DeterministicBacktestMetrics = {
  totalReturnPct: number | null;
  annualizedReturnPct: number | null;
  maxDrawdownPct: number | null;
  sharpeRatio: number | null;
  finalEquity: number | null;
  benchmarkReturnPct: number | null;
  excessReturnVsBenchmarkPct: number | null;
  buyAndHoldReturnPct: number | null;
  excessReturnVsBuyAndHoldPct: number | null;
  tradeCount: number;
  winCount: number;
  lossCount: number;
  winRatePct: number | null;
  avgTradeReturnPct: number | null;
  avgHoldingDays: number | null;
  avgHoldingBars: number | null;
  avgHoldingCalendarDays: number | null;
};

export type DeterministicBacktestBenchmarkMeta = {
  benchmarkLabel: string;
  buyHoldLabel: string;
  benchmarkSummary: RuleBacktestBenchmarkSummary;
  buyHoldSummary: RuleBacktestBenchmarkSummary | null;
  showBenchmark: boolean;
  showBuyHold: boolean;
};

export type DeterministicBacktestViewerMeta = {
  runId: number;
  code: string;
  status: string;
  primaryRowSource: 'auditRows' | 'mergedSeries';
  rowCount: number;
  firstDate: string | null;
  lastDate: string | null;
  strategySeriesLength: number;
  benchmarkSeriesLength: number;
  buyHoldSeriesLength: number;
  dailyPnlSeriesLength: number;
  positionSeriesLength: number;
  tradeEventCount: number;
};

export type DeterministicBacktestNormalizedResult = {
  rows: DeterministicBacktestNormalizedRow[];
  metrics: DeterministicBacktestMetrics;
  tradeEvents: DeterministicBacktestTradeEvent[];
  benchmarkMeta: DeterministicBacktestBenchmarkMeta;
  viewerMeta: DeterministicBacktestViewerMeta;
};

type MutableRow = DeterministicBacktestNormalizedRow;

const ACTION_LABELS: Record<string, string> = {
  buy: '买入',
  sell: '卖出',
  accumulate: '定投买入',
  forced_close: '期末平仓',
};

function safeNumber(value: unknown): number | null {
  if (value == null) return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function safeText(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function clampPosition(value: unknown): number | null {
  const resolved = safeNumber(value);
  if (resolved == null) return null;
  return Math.min(1, Math.max(0, resolved));
}

function createEmptyRow(date: string): MutableRow {
  return {
    date,
    strategyCumReturn: null,
    benchmarkCumReturn: null,
    buyHoldCumReturn: null,
    dailyPnl: null,
    dailyReturn: null,
    position: null,
    action: null,
    fillPrice: null,
    shares: null,
    cash: null,
    totalValue: null,
    holdingsValue: null,
    symbolClose: null,
    benchmarkClose: null,
    signalSummary: null,
    notes: null,
    fees: null,
    slippage: null,
    drawdownPct: null,
    positionState: null,
    unavailableReason: null,
  };
}

function mergeRow(
  rowsByDate: Map<string, MutableRow>,
  rawDate: unknown,
  patch: Partial<MutableRow>,
): void {
  const date = safeText(rawDate);
  if (!date) return;
  const current = rowsByDate.get(date) ?? createEmptyRow(date);
  rowsByDate.set(date, {
    ...current,
    ...Object.fromEntries(
      Object.entries(patch).filter(([, value]) => value !== undefined && value !== null),
    ),
  });
}

function deriveActionFromTrade(trade: RuleBacktestTradeItem, side: 'entry' | 'exit'): string {
  const raw = safeText(side === 'entry' ? trade.entryTrigger : trade.exitTrigger);
  if (raw === 'forced_close') return 'forced_close';
  return side === 'entry' ? 'buy' : 'sell';
}

function getBenchmarkMeta(run: RuleBacktestRunResponse, rows: DeterministicBacktestNormalizedRow[]): DeterministicBacktestBenchmarkMeta {
  const benchmarkSummary = run.benchmarkSummary || {};
  const buyHoldSummary = run.buyAndHoldSummary || null;
  const benchmarkLabel = String(benchmarkSummary.label || '基准');
  const buyHoldLabel = String(buyHoldSummary?.label || '当前标的买入并持有');
  const showBenchmark = rows.some((row) => row.benchmarkCumReturn != null) && benchmarkSummary.resolvedMode !== 'none';
  const showBuyHold = rows.some((row) => row.buyHoldCumReturn != null)
    && benchmarkSummary.resolvedMode !== 'none'
    && benchmarkSummary.resolvedMode !== 'same_symbol_buy_and_hold';

  return {
    benchmarkLabel,
    buyHoldLabel,
    benchmarkSummary,
    buyHoldSummary,
    showBenchmark,
    showBuyHold,
  };
}

function getMetrics(run: RuleBacktestRunResponse, rows: DeterministicBacktestNormalizedRow[]): DeterministicBacktestMetrics {
  const lastRow = rows.at(-1) ?? null;
  const totalReturnPct = safeNumber(run.totalReturnPct) ?? lastRow?.strategyCumReturn ?? null;
  const benchmarkSummaryReturnPct = safeNumber(run.benchmarkSummary?.returnPct);
  const buyHoldSummaryReturnPct = safeNumber(run.buyAndHoldSummary?.returnPct);
  const benchmarkReturnPct = safeNumber(run.benchmarkReturnPct) ?? benchmarkSummaryReturnPct ?? lastRow?.benchmarkCumReturn ?? null;
  const buyAndHoldReturnPct = safeNumber(run.buyAndHoldReturnPct) ?? buyHoldSummaryReturnPct ?? lastRow?.buyHoldCumReturn ?? null;
  const dailyReturns = rows
    .map((row) => row.dailyReturn)
    .filter((value): value is number => value != null && Number.isFinite(value));
  const sharpeRatio = (() => {
    if (dailyReturns.length < 2) return null;
    const mean = dailyReturns.reduce((sum, value) => sum + value, 0) / dailyReturns.length;
    const variance = dailyReturns.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (dailyReturns.length - 1);
    const stdDev = Math.sqrt(variance);
    if (!Number.isFinite(stdDev) || stdDev <= 0) return null;
    return Math.sqrt(252) * (mean / stdDev);
  })();

  return {
    totalReturnPct,
    annualizedReturnPct: safeNumber(run.annualizedReturnPct),
    maxDrawdownPct: safeNumber(run.maxDrawdownPct)
      ?? rows.reduce<number | null>((current, row) => {
        if (row.drawdownPct == null) return current;
        if (current == null) return row.drawdownPct;
        return Math.min(current, row.drawdownPct);
      }, null),
    sharpeRatio,
    finalEquity: safeNumber(run.finalEquity) ?? lastRow?.totalValue ?? null,
    benchmarkReturnPct,
    excessReturnVsBenchmarkPct: safeNumber(run.excessReturnVsBenchmarkPct)
      ?? (totalReturnPct != null && benchmarkReturnPct != null ? totalReturnPct - benchmarkReturnPct : null),
    buyAndHoldReturnPct,
    excessReturnVsBuyAndHoldPct: safeNumber(run.excessReturnVsBuyAndHoldPct)
      ?? (totalReturnPct != null && buyAndHoldReturnPct != null ? totalReturnPct - buyAndHoldReturnPct : null),
    tradeCount: Number(run.tradeCount ?? 0),
    winCount: Number(run.winCount ?? 0),
    lossCount: Number(run.lossCount ?? 0),
    winRatePct: safeNumber(run.winRatePct),
    avgTradeReturnPct: safeNumber(run.avgTradeReturnPct),
    avgHoldingDays: safeNumber(run.avgHoldingDays),
    avgHoldingBars: safeNumber(run.avgHoldingBars),
    avgHoldingCalendarDays: safeNumber(run.avgHoldingCalendarDays),
  };
}

function buildTradeEvents(
  rows: DeterministicBacktestNormalizedRow[],
  trades: RuleBacktestTradeItem[],
): DeterministicBacktestTradeEvent[] {
  const events: DeterministicBacktestTradeEvent[] = [];
  const seen = new Set<string>();
  const rowByDate = new Map(rows.map((row) => [row.date, row]));

  rows.forEach((row, index) => {
    if (!row.action) return;
    const key = `row:${row.date}:${row.action}:${row.fillPrice ?? 'na'}:${index}`;
    seen.add(key);
    events.push({
      key,
      date: row.date,
      action: row.action,
      fillPrice: row.fillPrice,
      shares: row.shares,
      cash: row.cash,
      totalValue: row.totalValue,
      signalDate: row.date,
      signalSummary: row.signalSummary,
      trigger: null,
      returnPct: null,
      holdingBars: null,
      notes: row.notes,
      source: 'row',
      tradeIndex: index,
    });
  });

  trades.forEach((trade, tradeIndex) => {
    const pushTradeEvent = (side: 'entry' | 'exit') => {
      const date = safeText(side === 'entry' ? trade.entryDate : trade.exitDate);
      if (!date) return;
      const action = deriveActionFromTrade(trade, side);
      const fillPrice = safeNumber(side === 'entry' ? trade.entryPrice : trade.exitPrice);
      const dedupeKey = `trade:${date}:${action}:${fillPrice ?? 'na'}:${tradeIndex}`;
      if (seen.has(dedupeKey)) return;
      seen.add(dedupeKey);
      const row = rowByDate.get(date);
      events.push({
        key: dedupeKey,
        date,
        action,
        fillPrice,
        shares: row?.shares ?? null,
        cash: row?.cash ?? null,
        totalValue: row?.totalValue ?? null,
        signalDate: safeText(side === 'entry' ? trade.entrySignalDate : trade.exitSignalDate),
        signalSummary: safeText(side === 'entry' ? trade.entrySignal : trade.exitSignal) ?? row?.signalSummary ?? null,
        trigger: safeText(side === 'entry' ? trade.entryTrigger : trade.exitTrigger),
        returnPct: safeNumber(trade.returnPct),
        holdingBars: safeNumber(trade.holdingBars),
        notes: safeText(trade.notes),
        source: 'trade',
        tradeIndex,
      });
    };

    pushTradeEvent('entry');
    pushTradeEvent('exit');
  });

  return events.sort((left, right) => {
    if (left.date === right.date) {
      if (left.tradeIndex === right.tradeIndex) return left.key.localeCompare(right.key);
      return (left.tradeIndex ?? 0) - (right.tradeIndex ?? 0);
    }
    return left.date.localeCompare(right.date);
  });
}

function populateFromAuditRows(rowsByDate: Map<string, MutableRow>, auditRows: RuleBacktestAuditRowItem[]): void {
  auditRows.forEach((row) => {
    mergeRow(rowsByDate, row.date, {
      symbolClose: safeNumber(row.symbolClose),
      benchmarkClose: safeNumber(row.benchmarkClose),
      signalSummary: safeText(row.signalSummary),
      position: clampPosition(row.position ?? row.exposurePct ?? row.targetPosition),
      action: safeText(row.action ?? row.executedAction),
      fillPrice: safeNumber(row.fillPrice),
      shares: safeNumber(row.shares ?? row.sharesHeld),
      cash: safeNumber(row.cash),
      holdingsValue: safeNumber(row.holdingsValue),
      totalValue: safeNumber(row.totalPortfolioValue),
      positionState: safeText(row.positionState),
      dailyPnl: safeNumber(row.dailyPnl),
      dailyReturn: safeNumber(row.dailyReturn ?? row.dailyReturnPct),
      strategyCumReturn: safeNumber(row.cumulativeReturn ?? row.cumulativeStrategyReturnPct),
      benchmarkCumReturn: safeNumber(row.benchmarkCumulativeReturn ?? row.cumulativeBenchmarkReturnPct),
      buyHoldCumReturn: safeNumber(row.buyHoldCumulativeReturn ?? row.cumulativeBuyAndHoldReturnPct),
      fees: safeNumber(row.fees),
      slippage: safeNumber(row.slippage),
      notes: safeText(row.notes),
      unavailableReason: safeText(row.unavailableReason),
      drawdownPct: safeNumber(row.drawdownPct),
    });
  });
}

export function formatDeterministicActionLabel(action?: string | null): string {
  if (!action) return '--';
  return ACTION_LABELS[action] || action;
}

export function normalizeDeterministicBacktestResult(run: RuleBacktestRunResponse): DeterministicBacktestNormalizedResult {
  const rowsByDate = new Map<string, MutableRow>();
  const auditRows = Array.isArray(run.auditRows) ? run.auditRows : [];
  populateFromAuditRows(rowsByDate, auditRows);

  if (auditRows.length === 0) {
    (run.equityCurve || []).forEach((point) => {
      mergeRow(rowsByDate, point.date, {
        strategyCumReturn: safeNumber(point.cumulativeReturnPct),
        position: clampPosition(point.exposurePct ?? point.targetPosition),
        action: safeText(point.executedAction),
        fillPrice: safeNumber(point.fillPrice),
        shares: safeNumber(point.sharesHeld),
        cash: safeNumber(point.cash),
        holdingsValue: safeNumber(point.holdingsValue),
        totalValue: safeNumber(point.totalPortfolioValue ?? point.equity),
        symbolClose: safeNumber(point.close),
        signalSummary: safeText(point.signalSummary),
        notes: safeText(point.notes),
        fees: safeNumber(point.feeAmount),
        slippage: safeNumber(point.slippageAmount),
        drawdownPct: safeNumber(point.drawdownPct),
        positionState: safeText(point.positionState),
      });
    });

    (run.benchmarkCurve || []).forEach((point) => {
      mergeRow(rowsByDate, point.date, {
        benchmarkCumReturn: safeNumber(point.cumulativeReturnPct),
        benchmarkClose: safeNumber(point.close),
      });
    });

    (run.buyAndHoldCurve || []).forEach((point) => {
      mergeRow(rowsByDate, point.date, {
        buyHoldCumReturn: safeNumber(point.cumulativeReturnPct),
      });
    });

    (run.dailyReturnSeries || []).forEach((point) => {
      mergeRow(rowsByDate, point.date, {
        dailyPnl: safeNumber(point.dailyPnl),
        dailyReturn: safeNumber(point.dailyReturnPct),
        totalValue: safeNumber(point.equity),
      });
    });

    (run.exposureCurve || []).forEach((point) => {
      mergeRow(rowsByDate, point.date, {
        position: clampPosition(point.exposure),
        positionState: safeText(point.positionState),
        action: safeText(point.executedAction),
        fillPrice: safeNumber(point.fillPrice),
      });
    });
  }

  const rows = Array.from(rowsByDate.values())
    .sort((left, right) => left.date.localeCompare(right.date))
    .map((row) => {
      if (row.strategyCumReturn == null && row.totalValue != null && run.initialCapital > 0) {
        row.strategyCumReturn = ((row.totalValue - run.initialCapital) / run.initialCapital) * 100;
      }
      return row;
    });

  const tradeEvents = buildTradeEvents(rows, run.trades || []);
  const benchmarkMeta = getBenchmarkMeta(run, rows);
  const metrics = getMetrics(run, rows);
  const viewerMeta: DeterministicBacktestViewerMeta = {
    runId: run.id,
    code: run.code,
    status: run.status,
    primaryRowSource: auditRows.length > 0 ? 'auditRows' : 'mergedSeries',
    rowCount: rows.length,
    firstDate: rows[0]?.date ?? null,
    lastDate: rows.at(-1)?.date ?? null,
    strategySeriesLength: rows.filter((row) => row.strategyCumReturn != null).length,
    benchmarkSeriesLength: rows.filter((row) => row.benchmarkCumReturn != null).length,
    buyHoldSeriesLength: rows.filter((row) => row.buyHoldCumReturn != null).length,
    dailyPnlSeriesLength: rows.filter((row) => row.dailyPnl != null).length,
    positionSeriesLength: rows.filter((row) => row.position != null).length,
    tradeEventCount: tradeEvents.length,
  };

  return {
    rows,
    metrics,
    tradeEvents,
    benchmarkMeta,
    viewerMeta,
  };
}
