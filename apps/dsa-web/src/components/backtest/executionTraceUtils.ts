import type {
  RuleBacktestExecutionTracePayload,
  RuleBacktestExecutionTraceRowItem,
  RuleBacktestRunResponse,
} from '../../types/backtest';
import { formatDeterministicActionLabel } from './normalizeDeterministicBacktestResult';

type TraceExportColumn = {
  key: keyof RuleBacktestExecutionTraceRowItem | 'actionDisplay';
  label: string;
};

const TRACE_EXPORT_COLUMNS: TraceExportColumn[] = [
  { key: 'date', label: '日期' },
  { key: 'symbolClose', label: '标的收盘价' },
  { key: 'benchmarkClose', label: '基准收盘价' },
  { key: 'signalSummary', label: '信号摘要' },
  { key: 'actionDisplay', label: '动作' },
  { key: 'fillPrice', label: '成交价' },
  { key: 'shares', label: '持股数' },
  { key: 'cash', label: '现金' },
  { key: 'holdingsValue', label: '持仓市值' },
  { key: 'totalPortfolioValue', label: '总资产' },
  { key: 'dailyPnl', label: '当日盈亏' },
  { key: 'dailyReturn', label: '当日收益率' },
  { key: 'cumulativeReturn', label: '策略累计收益率' },
  { key: 'benchmarkCumulativeReturn', label: '基准累计收益率' },
  { key: 'buyHoldCumulativeReturn', label: '买入持有累计收益率' },
  { key: 'position', label: '仓位' },
  { key: 'fees', label: '手续费' },
  { key: 'slippage', label: '滑点' },
  { key: 'notes', label: '备注' },
  { key: 'assumptionsDefaults', label: 'assumptions' },
  { key: 'fallback', label: 'fallback' },
];

function stringifyCell(value: unknown): string {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function getFallbackAuditTraceRows(run: RuleBacktestRunResponse): RuleBacktestExecutionTraceRowItem[] {
  return (run.auditRows || []).map((row) => ({
    date: row.date || null,
    symbolClose: row.symbolClose ?? null,
    benchmarkClose: row.benchmarkClose ?? null,
    signalSummary: row.signalSummary ?? null,
    action: row.action ?? row.executedAction ?? null,
    actionDisplay: formatDeterministicActionLabel(row.action ?? row.executedAction),
    fillPrice: row.fillPrice ?? null,
    shares: row.shares ?? row.sharesHeld ?? null,
    cash: row.cash ?? null,
    holdingsValue: row.holdingsValue ?? null,
    totalPortfolioValue: row.totalPortfolioValue ?? null,
    dailyPnl: row.dailyPnl ?? null,
    dailyReturn: row.dailyReturn ?? row.dailyReturnPct ?? null,
    cumulativeReturn: row.cumulativeReturn ?? row.cumulativeStrategyReturnPct ?? null,
    benchmarkCumulativeReturn: row.benchmarkCumulativeReturn ?? row.cumulativeBenchmarkReturnPct ?? null,
    buyHoldCumulativeReturn: row.buyHoldCumulativeReturn ?? row.cumulativeBuyAndHoldReturnPct ?? null,
    position: row.position ?? row.exposurePct ?? row.targetPosition ?? null,
    fees: row.fees ?? null,
    slippage: row.slippage ?? null,
    notes: row.notes ?? null,
    unavailableReason: row.unavailableReason ?? null,
    fallback: row.unavailableReason ?? null,
  }));
}

function downloadBlob(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function getExecutionTracePayload(run: RuleBacktestRunResponse): RuleBacktestExecutionTracePayload | null {
  if (run.executionTrace && typeof run.executionTrace === 'object') {
    return run.executionTrace;
  }
  return null;
}

export function getExecutionTraceRows(run: RuleBacktestRunResponse): RuleBacktestExecutionTraceRowItem[] {
  const rows = getExecutionTracePayload(run)?.rows;
  if (Array.isArray(rows) && rows.length > 0) {
    return rows;
  }
  return getFallbackAuditTraceRows(run);
}

export function hasExecutionTraceRows(run: RuleBacktestRunResponse): boolean {
  return getExecutionTraceRows(run).length > 0;
}

export function getExecutionTraceSourceLabel(source?: string | null): string {
  const normalized = String(source || '').trim();
  if (!normalized) return '--';
  if (normalized === 'storedExecutionTrace') return '已存储 execution_trace';
  if (normalized === 'rebuiltFromStoredAuditRows') return '由历史 audit rows 回补';
  return normalized;
}

export function buildExecutionTraceExportRows(run: RuleBacktestRunResponse): Array<Record<string, string>> {
  return getExecutionTraceRows(run).map((row) => {
    const exportRow: Record<string, string> = {};
    TRACE_EXPORT_COLUMNS.forEach(({ key, label }) => {
      const value = key === 'actionDisplay'
        ? row.actionDisplay || formatDeterministicActionLabel(row.action)
        : row[key];
      exportRow[label] = stringifyCell(value);
    });
    return exportRow;
  });
}

export function downloadExecutionTraceCsv(run: RuleBacktestRunResponse): void {
  const rows = buildExecutionTraceExportRows(run);
  if (rows.length === 0) return;

  const header = TRACE_EXPORT_COLUMNS.map((column) => column.label);
  const content = [header, ...rows.map((row) => header.map((key) => `"${String(row[key] || '').replaceAll('"', '""')}"`))]
    .map((row) => row.join(','))
    .join('\n');

  downloadBlob(
    `backtest-execution-trace-${run.code}-${run.id}.csv`,
    `\uFEFF${content}`,
    'text/csv;charset=utf-8',
  );
}

export function downloadExecutionTraceJson(run: RuleBacktestRunResponse): void {
  const payload = getExecutionTracePayload(run);
  const content = JSON.stringify({
    runId: run.id,
    code: run.code,
    status: run.status,
    source: payload?.source || null,
    traceRows: buildExecutionTraceExportRows(run),
    assumptions: payload?.assumptionsDefaults || {},
    executionModel: payload?.executionModel || {},
    executionAssumptions: payload?.executionAssumptions || {},
    fallback: payload?.fallback || {},
  }, null, 2);

  downloadBlob(
    `backtest-execution-trace-${run.code}-${run.id}.json`,
    content,
    'application/json;charset=utf-8',
  );
}
