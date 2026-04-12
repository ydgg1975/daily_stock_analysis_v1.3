/* eslint-disable react-refresh/only-export-components */
import type React from 'react';
import { Badge, Button } from '../../components/common';
import type {
  AssumptionMap,
  BacktestResultItem,
  BacktestRunHistoryItem,
  BacktestRunResponse,
  RuleBacktestHistoryItem,
  RuleBacktestParseResponse,
  RuleBacktestRunResponse,
  RuleBacktestTradeItem,
} from '../../types/backtest';

const ASSUMPTION_LABELS: Record<string, string> = {
  module_type: '模块语义',
  evaluation_window_unit: '评估窗口单位',
  maturity_unit: '成熟期单位',
  price_basis: '价格口径',
  analysis_signal_timing: '分析信号时点',
  simulated_entry_timing: '模拟入场时点',
  simulated_exit_timing: '模拟离场时点',
  position_sizing: '仓位假设',
  fees_slippage: '费用与滑点',
  timeframe: '时间周期',
  signal_evaluation_timing: '信号评估时点',
  entry_fill_timing: '入场成交时点',
  exit_fill_timing: '离场成交时点',
  position_sizing_model: '仓位模型',
  fee_model: '手续费模型',
  fee_bps_per_side: '单边手续费',
  slippage_model: '滑点模型',
  slippage_bps_per_side: '单边滑点',
  benchmark_method: '基准比较',
};

const RULE_STATUS_LABELS: Record<string, string> = {
  parsing: '解析中',
  queued: '排队中',
  running: '运行中',
  summarizing: '整理摘要',
  completed: '已完成',
  cancelled: '已取消',
  failed: '失败',
};

const TERMINAL_RULE_STATUSES = new Set(['completed', 'failed', 'cancelled']);
const CANCELLABLE_RULE_STATUSES = new Set(['queued', 'parsing', 'running', 'summarizing']);

const HISTORICAL_STATUS_LABELS: Record<string, string> = {
  completed: '已完成',
  error: '执行异常',
  insufficient_data: '样本不足',
};

export function pct(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value.toFixed(2)}%`;
}

export function formatNumber(value?: number | null, digits = 2): string {
  if (value == null || Number.isNaN(value)) return '--';
  return value.toFixed(digits);
}

export function formatDateTime(value?: string | null): string {
  if (!value) return '--';
  return value.replace('T', ' ').replace('Z', '');
}

export function toDateInputValue(value: Date): string {
  return value.toISOString().slice(0, 10);
}

export function getDefaultRuleDateRange(): { startDate: string; endDate: string } {
  const end = new Date();
  const start = new Date(end);
  start.setFullYear(end.getFullYear() - 1);
  return {
    startDate: toDateInputValue(start),
    endDate: toDateInputValue(end),
  };
}

export type RuleBenchmarkMode =
  | 'auto'
  | 'none'
  | 'same_symbol_buy_and_hold'
  | 'index_hs300'
  | 'index_csi500'
  | 'index_ndx100'
  | 'etf_qqq'
  | 'index_sp500'
  | 'etf_spy'
  | 'custom_code';

export const RULE_BENCHMARK_OPTIONS: Array<{ value: RuleBenchmarkMode; label: string }> = [
  { value: 'auto', label: '自动' },
  { value: 'none', label: '无基准' },
  { value: 'same_symbol_buy_and_hold', label: '当前标的买入并持有' },
  { value: 'index_hs300', label: '沪深300' },
  { value: 'index_csi500', label: '中证500' },
  { value: 'index_ndx100', label: '纳指100' },
  { value: 'etf_qqq', label: 'QQQ' },
  { value: 'index_sp500', label: '标普500' },
  { value: 'etf_spy', label: 'SPY' },
  { value: 'custom_code', label: '自定义代码' },
];

function isAshareLikeCode(code: string): boolean {
  const normalized = String(code || '').trim().toUpperCase();
  return /^\d{6}$/.test(normalized);
}

function isUsLikeCode(code: string): boolean {
  const normalized = String(code || '').trim().toUpperCase();
  return /^[A-Z^]{1,5}(\.[A-Z])?$/.test(normalized);
}

export function getAutoBenchmarkMode(code: string): RuleBenchmarkMode {
  if (isAshareLikeCode(code)) return 'index_hs300';
  if (isUsLikeCode(code)) return 'etf_qqq';
  return 'same_symbol_buy_and_hold';
}

export function getBenchmarkModeLabel(mode: RuleBenchmarkMode, code?: string, customCode?: string): string {
  if (mode === 'auto') {
    return `自动 · ${getBenchmarkModeLabel(getAutoBenchmarkMode(code || ''), code, customCode)}`;
  }
  if (mode === 'custom_code') {
    const normalizedCustomCode = String(customCode || '').trim().toUpperCase();
    return normalizedCustomCode ? `自定义 · ${normalizedCustomCode}` : '自定义代码';
  }
  const matched = RULE_BENCHMARK_OPTIONS.find((item) => item.value === mode);
  return matched?.label || '基准';
}

export function parsePositiveInt(value: string, fallback: number, minimum = 1): number {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(minimum, parsed);
}

function formatAssumptionValue(value: unknown): string {
  if (value == null) return '--';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (Array.isArray(value)) return value.join(', ');
  return String(value);
}

function getSetupValue(setup: Record<string, unknown> | undefined, key: string): unknown {
  if (!setup) return undefined;
  if (key in setup) return setup[key];
  const camelKey = key.replace(/_([a-z])/g, (_, ch: string) => ch.toUpperCase());
  if (camelKey in setup) return setup[camelKey];
  return undefined;
}

export function getStrategySpecValue(spec: Record<string, unknown> | undefined, path: string[]): unknown {
  let current: unknown = spec;
  for (const segment of path) {
    if (!current || typeof current !== 'object') {
      return undefined;
    }
    const record = current as Record<string, unknown>;
    const camelSegment = segment.replace(/_([a-z])/g, (_, ch: string) => ch.toUpperCase());
    if (segment in record) {
      current = record[segment];
      continue;
    }
    if (camelSegment in record) {
      current = record[camelSegment];
      continue;
    }
    return undefined;
  }
  return current;
}

export function getStrategyPreviewSpec(parsed: RuleBacktestParseResponse | null): Record<string, unknown> | undefined {
  const direct = parsed?.parsedStrategy.strategySpec;
  if (direct && typeof direct === 'object') return direct;
  const fallback = parsed?.parsedStrategy.setup;
  return fallback && typeof fallback === 'object' ? fallback : undefined;
}

function getSetupString(setup: Record<string, unknown> | undefined, key: string): string {
  const value = getSetupValue(setup, key);
  if (value == null || value === '') return '--';
  return String(value);
}

function getSetupNumber(setup: Record<string, unknown> | undefined, key: string): number | null {
  const value = getSetupValue(setup, key);
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function getPeriodicString(source: Record<string, unknown> | undefined, key: string): string {
  const strategyType = getStrategySpecValue(source, ['strategy_type']);
  if (strategyType === 'periodic_accumulation') {
    const fromSpec = {
      symbol: getStrategySpecValue(source, ['symbol']),
      start_date: getStrategySpecValue(source, ['date_range', 'start_date']),
      end_date: getStrategySpecValue(source, ['date_range', 'end_date']),
      execution_frequency: getStrategySpecValue(source, ['schedule', 'frequency']),
      execution_price_basis: getStrategySpecValue(source, ['entry', 'price_basis']),
      cash_policy: getStrategySpecValue(source, ['position_behavior', 'cash_policy']),
      exit_policy: getStrategySpecValue(source, ['exit', 'policy']),
      execution_timing: getStrategySpecValue(source, ['schedule', 'timing']),
    }[key];
    if (fromSpec != null && fromSpec !== '') return String(fromSpec);
  }
  return getSetupString(source, key);
}

export function getPeriodicNumber(source: Record<string, unknown> | undefined, key: string): number | null {
  const strategyType = getStrategySpecValue(source, ['strategy_type']);
  if (strategyType === 'periodic_accumulation') {
    const fromSpec = {
      initial_capital: getStrategySpecValue(source, ['capital', 'initial_capital']),
      quantity_per_trade: getStrategySpecValue(source, ['entry', 'order', 'quantity']),
      amount_per_trade: getStrategySpecValue(source, ['entry', 'order', 'amount']),
      fee_bps: getStrategySpecValue(source, ['costs', 'fee_bps']),
      slippage_bps: getStrategySpecValue(source, ['costs', 'slippage_bps']),
    }[key];
    if (fromSpec != null && fromSpec !== '') {
      const parsed = Number(fromSpec);
      return Number.isFinite(parsed) ? parsed : null;
    }
  }
  return getSetupNumber(source, key);
}

export function formatDraftOrder(source: Record<string, unknown> | undefined): string {
  const orderMode = String(getStrategySpecValue(source, ['entry', 'order', 'mode']) || getSetupString(source, 'order_mode'));
  if (orderMode === 'fixed_amount') {
    const amount = getPeriodicNumber(source, 'amount_per_trade');
    return amount != null ? `${amount} 元 / 次` : '--';
  }
  const quantity = getPeriodicNumber(source, 'quantity_per_trade');
  return quantity != null ? `${quantity} 股 / 次` : '--';
}

export function formatCashPolicy(source: Record<string, unknown> | undefined): string {
  const value = getPeriodicString(source, 'cash_policy');
  if (value === 'stop_when_insufficient_cash') return '现金不足时停止';
  if (value === 'skip_when_insufficient_cash') return '现金不足时跳过';
  return '--';
}

export function formatExecutionPriceBasis(source: Record<string, unknown> | undefined): string {
  const value = getPeriodicString(source, 'execution_price_basis');
  if (value === 'open') return '当日开盘价';
  if (value === 'next_bar_open') return '下一根开盘价';
  if (value === 'close') return '收盘价';
  return '--';
}

export function formatExitPolicy(source: Record<string, unknown> | undefined): string {
  const value = getPeriodicString(source, 'exit_policy');
  if (value === 'close_at_end') return '到期统一平仓';
  return '--';
}

export function buildPeriodicAssumptions(source: Record<string, unknown> | undefined): string[] {
  const items: string[] = [];
  if (getPeriodicString(source, 'execution_price_basis') === 'open') {
    items.push('“开市价 / 开盘价”按当日开盘价成交。');
  }
  if (getPeriodicString(source, 'execution_frequency') === 'daily') {
    items.push('“每天买入”按每个交易日尝试一次，并持续累积仓位。');
  }
  if (getPeriodicString(source, 'cash_policy') === 'stop_when_insufficient_cash') {
    items.push('现金不足以完成单次买入时，后续停止继续买入。');
  }
  if (getPeriodicString(source, 'exit_policy') === 'close_at_end') {
    items.push('未写卖出规则时，回测结束日统一平仓。');
  }
  return items;
}

function getAssumptionEntries(assumptions?: AssumptionMap): Array<{ key: string; label: string; value: string }> {
  return Object.entries(assumptions || {})
    .filter(([, value]) => value != null && value !== '')
    .map(([key, value]) => ({
      key,
      label: ASSUMPTION_LABELS[key] || key.replace(/_/g, ' '),
      value: formatAssumptionValue(value),
    }));
}

function formatIndicatorEntries(snapshot?: Record<string, unknown>): Array<{ key: string; value: string }> {
  return Object.entries(snapshot || {})
    .filter(([, value]) => value != null)
    .slice(0, 6)
    .map(([key, value]) => ({
      key,
      value: typeof value === 'number' ? value.toFixed(2) : String(value),
    }));
}

export function isRuleRunTerminal(status?: string): boolean {
  return TERMINAL_RULE_STATUSES.has(String(status || '').trim().toLowerCase());
}

export function canCancelRuleRun(status?: string): boolean {
  return CANCELLABLE_RULE_STATUSES.has(String(status || '').trim().toLowerCase());
}

export function getRuleRunStatusDescription(status?: string): string {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'parsing') return '正在解析策略文本并整理可执行规则。';
  if (normalized === 'queued') return '任务已入队，等待后台开始执行。';
  if (normalized === 'running') return '后台正在执行回测，会持续刷新状态。';
  if (normalized === 'summarizing') return '回测已算完，正在整理摘要、交易和执行轨迹。';
  if (normalized === 'completed') return '回测已完成，可以查看结果摘要、交易和执行轨迹。';
  if (normalized === 'cancelled') return '回测已取消，当前运行不会继续推进。';
  if (normalized === 'failed') return '回测执行失败，可以返回配置页调整后重试。';
  return '规则回测已提交。';
}

export function getRuleRunStatusTone(status?: string): 'default' | 'success' | 'warning' | 'danger' | 'info' {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'completed') return 'success';
  if (normalized === 'failed') return 'danger';
  if (normalized === 'summarizing') return 'info';
  if (normalized === 'cancelled') return 'warning';
  if (normalized === 'running' || normalized === 'queued' || normalized === 'parsing') return 'warning';
  return 'default';
}

export function getHistoricalStatusBadge(status?: string) {
  const normalized = status || 'completed';
  const label = HISTORICAL_STATUS_LABELS[normalized] || normalized;
  if (normalized === 'completed') return <Badge variant="success">{label}</Badge>;
  if (normalized === 'insufficient_data') return <Badge variant="warning">{label}</Badge>;
  if (normalized === 'error') return <Badge variant="danger">{label}</Badge>;
  return <Badge variant="default">{label}</Badge>;
}

export function getRuleStatusBadge(status?: string) {
  const normalized = status || 'queued';
  const label = RULE_STATUS_LABELS[normalized] || normalized;
  if (normalized === 'completed') return <Badge variant="success">{label}</Badge>;
  if (normalized === 'failed') return <Badge variant="danger">{label}</Badge>;
  if (normalized === 'summarizing') return <Badge variant="info">{label}</Badge>;
  if (normalized === 'cancelled') return <Badge variant="warning">{label}</Badge>;
  if (normalized === 'running') return <Badge variant="warning">{label}</Badge>;
  return <Badge variant="default">{label}</Badge>;
}

export function getRuleRunStatusLabel(status?: string): string {
  const normalized = String(status || 'queued').trim().toLowerCase();
  return RULE_STATUS_LABELS[normalized] || normalized;
}

export function getHistoricalRequestedModeLabel(mode?: string | null): string {
  const normalized = String(mode || '').trim().toLowerCase();
  if (!normalized) return '--';
  if (normalized === 'local_first') return '本地优先（优先读 LocalParquet）';
  if (normalized === 'api_first') return '远端优先';
  if (normalized === 'auto') return '自动选择';
  return String(mode);
}

export function getHistoricalResolvedSourceLabel(source?: string | null): string {
  const normalized = String(source || '').trim();
  if (normalized === 'LocalParquet') return 'LocalParquet 本地文件';
  if (normalized === 'DatabaseCache') return '数据库缓存';
  if (normalized === 'YfinanceFetcher') return 'Yfinance 在线回退';
  if (normalized === 'MixedFallback') return '混合回退路径';
  if (normalized === 'Unknown') return '未知来源';
  return normalized || '--';
}

export function getHistoricalFallbackLabel(value?: boolean | null): string {
  if (value == null) return '--';
  return value ? '已回退' : '未回退';
}

export function describeHistoricalDataSource(meta: {
  requestedMode?: string | null;
  resolvedSource?: string | null;
  fallbackUsed?: boolean | null;
}): {
  tone: 'success' | 'warning' | 'info';
  title: string;
  body: string;
  detail: string;
} {
  const requestedLabel = getHistoricalRequestedModeLabel(meta.requestedMode);
  const resolvedLabel = getHistoricalResolvedSourceLabel(meta.resolvedSource);
  const fallbackLabel = getHistoricalFallbackLabel(meta.fallbackUsed);

  if (meta.resolvedSource === 'LocalParquet' && meta.fallbackUsed === false) {
    return {
      tone: 'success',
      title: '已命中 LocalParquet',
      body: '本次样本与评估优先读取本地 Parquet，没有走回退路径。',
      detail: `请求模式：${requestedLabel} · 实际来源：${resolvedLabel} · 回退：${fallbackLabel}`,
    };
  }

  if (meta.fallbackUsed) {
    return {
      tone: 'warning',
      title: `已回退到 ${resolvedLabel}`,
      body: '系统仍按本地优先发起，但本次实际使用了回退路径。通常表示本地数据缺失、不可用，或覆盖范围不足。',
      detail: `请求模式：${requestedLabel} · 实际来源：${resolvedLabel} · 回退：${fallbackLabel}`,
    };
  }

  if (meta.resolvedSource) {
    return {
      tone: 'info',
      title: `当前使用 ${resolvedLabel}`,
      body: '这里显示的是本次实际命中的数据路径，便于确认是否按预期读取。',
      detail: `请求模式：${requestedLabel} · 实际来源：${resolvedLabel} · 回退：${fallbackLabel}`,
    };
  }

  return {
    tone: 'info',
    title: '等待生成数据源诊断',
    body: '准备样本或运行评估后，这里会显示本次请求的实际数据路径。',
    detail: `请求模式：${requestedLabel} · 实际来源：${resolvedLabel} · 回退：${fallbackLabel}`,
  };
}

function renderDirectionBadge(correct?: boolean | null, expected?: string | null) {
  if (correct === true) return <span className="product-direction product-direction--positive">✓ {expected || '匹配'}</span>;
  if (correct === false) return <span className="product-direction product-direction--negative">✕ {expected || '偏离'}</span>;
  return <span className="product-direction">--</span>;
}

export const SectionEyebrow: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span className="product-kicker">{children}</span>
);

export const MetricCard: React.FC<{
  label: string;
  value: string;
  tone?: 'default' | 'positive' | 'negative' | 'accent';
  note?: string;
}> = ({ label, value, tone = 'default', note }) => (
  <div className={`metric-card metric-card--${tone}`}>
    <p className="metric-card__label">{label}</p>
    <p className="metric-card__value">{value}</p>
    {note ? <p className="metric-card__note">{note}</p> : null}
  </div>
);

export const SummaryStrip: React.FC<{
  items: Array<{ label: string; value: string; note?: string }>;
}> = ({ items }) => (
  <div className="summary-strip" role="list">
    {items.map((item) => (
      <div key={item.label} className="summary-strip__item" role="listitem">
        <p className="summary-strip__label">{item.label}</p>
        <p className="summary-strip__value">{item.value}</p>
        {item.note ? <p className="summary-strip__note">{item.note}</p> : null}
      </div>
    ))}
  </div>
);

export const Banner: React.FC<{
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  title: React.ReactNode;
  body?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}> = ({ tone = 'default', title, body, actions, className }) => (
  <div className={`product-banner product-banner--${tone}${className ? ` ${className}` : ''}`}>
    <div className="product-banner__copy">
      <p className="product-banner__title">{title}</p>
      {body ? <div className="product-banner__body">{body}</div> : null}
    </div>
    {actions ? <div className="product-banner__actions">{actions}</div> : null}
  </div>
);

export const Disclosure: React.FC<{
  summary: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}> = ({ summary, children, defaultOpen = false }) => (
  <details className="product-disclosure" open={defaultOpen}>
    <summary className="product-disclosure__summary">{summary}</summary>
    <div className="product-disclosure__body">{children}</div>
  </details>
);

export const AssumptionList: React.FC<{
  assumptions?: AssumptionMap;
  emptyText: string;
}> = ({ assumptions, emptyText }) => {
  const entries = getAssumptionEntries(assumptions);

  if (entries.length === 0) {
    return <p className="product-empty-note">{emptyText}</p>;
  }

  return (
    <dl className="audit-grid">
      {entries.map((item) => (
        <div key={item.key} className="audit-grid__row">
          <dt className="audit-grid__label">{item.label}</dt>
          <dd className="audit-grid__value">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
};

export const HistoricalRunSummary: React.FC<{ data: BacktestRunResponse }> = ({ data }) => (
  <Banner
    tone="info"
    title="历史评估已更新"
    body={(
      <>
        已处理 {data.processed} 条候选，写入 {data.saved} 条结果，完成 {data.completed} 条评估。
        <span className="product-banner__meta">
          样本不足 {data.insufficient} 条，异常 {data.errors} 条，候选 {data.candidateCount} 条。
        </span>
        {data.noResultMessage ? <span className="product-banner__meta">{data.noResultMessage}</span> : null}
      </>
    )}
  />
);

export const RuleRunStatusBanner: React.FC<{ run: RuleBacktestRunResponse }> = ({ run }) => {
  const latestStatusAt = run.statusHistory?.[run.statusHistory.length - 1]?.at;
  const tone = getRuleRunStatusTone(run.status);
  const statusDescription = getRuleRunStatusDescription(run.status);

  return (
    <Banner
      tone={tone}
      title={(
        <span className="flex flex-wrap items-center gap-2">
          规则任务状态
          {getRuleStatusBadge(run.status)}
        </span>
      )}
      body={(
        <>
          {run.statusMessage || statusDescription}
          <span className="product-banner__meta">
            运行 #{run.id} · {run.code} · {latestStatusAt ? formatDateTime(latestStatusAt) : '--'}
          </span>
          {run.noResultMessage ? <span className="product-banner__meta">{run.noResultMessage}</span> : null}
        </>
      )}
    />
  );
};

export const HistoricalResultsTable: React.FC<{ rows: BacktestResultItem[] }> = ({ rows }) => {
  if (rows.length === 0) {
    return <div className="product-empty-state">暂无历史分析评估结果。先准备样本或运行一次评估。</div>;
  }

  return (
    <div className="product-table-shell">
      <table className="product-table">
        <thead>
          <tr>
            <th>日期</th>
            <th>代码</th>
            <th>建议</th>
            <th>方向</th>
            <th className="product-table__align-right">模拟收益</th>
            <th className="product-table__align-right">标的收益</th>
            <th>实际数据源</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.analysisHistoryId}>
              <td>{row.analysisDate || '--'}</td>
              <td className="product-table__mono">{row.code}</td>
              <td>{row.operationAdvice || '--'}</td>
              <td>{renderDirectionBadge(row.directionCorrect, row.directionExpected)}</td>
              <td className="product-table__align-right">{pct(row.simulatedReturnPct)}</td>
              <td className="product-table__align-right">{pct(row.stockReturnPct)}</td>
              <td>{row.marketDataSources.length > 0 ? row.marketDataSources.join(', ') : '--'}</td>
              <td>{getHistoricalStatusBadge(row.evalStatus)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export const HistoricalRunsTable: React.FC<{
  rows: BacktestRunHistoryItem[];
  selectedRunId: number | null;
  onOpen: (run: BacktestRunHistoryItem) => void;
}> = ({ rows, selectedRunId, onOpen }) => {
  if (rows.length === 0) {
    return <div className="product-empty-state">暂无历史分析评估运行记录。</div>;
  }

  return (
    <div className="product-table-shell">
      <table className="product-table">
        <thead>
          <tr>
            <th>运行时间</th>
            <th>代码</th>
            <th>窗口定义</th>
            <th className="product-table__align-right">候选</th>
            <th className="product-table__align-right">胜率</th>
            <th className="product-table__align-right">平均模拟收益</th>
            <th>状态</th>
            <th className="product-table__align-right">操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} data-active={selectedRunId === row.id ? 'true' : 'false'}>
              <td>{formatDateTime(row.runAt)}</td>
              <td className="product-table__mono">{row.code || '--'}</td>
              <td>{row.evaluationWindowTradingBars || row.evalWindowDays} bars / {row.maturityCalendarDays || row.minAgeDays} 天</td>
              <td className="product-table__align-right">{row.candidateCount}</td>
              <td className="product-table__align-right">{pct(row.winRatePct)}</td>
              <td className="product-table__align-right">{pct(row.avgSimulatedReturnPct)}</td>
              <td>{getHistoricalStatusBadge(row.status)}</td>
              <td className="product-table__align-right">
                <Button size="sm" variant="ghost" onClick={() => onOpen(row)}>
                  查看
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export const RuleBacktestTradeTable: React.FC<{ trades: RuleBacktestTradeItem[] }> = ({ trades }) => {
  if (trades.length === 0) {
    return <div className="product-empty-state">暂无交易明细。</div>;
  }

  return (
    <div className="product-table-shell">
      <table className="product-table product-table--wide">
        <thead>
          <tr>
            <th>信号与成交</th>
            <th>入场触发</th>
            <th>离场触发</th>
            <th>指标快照</th>
            <th className="product-table__align-right">收益</th>
            <th className="product-table__align-right">持有</th>
            <th>执行审计</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade, index) => {
            const entryIndicators = formatIndicatorEntries(trade.entryIndicators);
            const exitIndicators = formatIndicatorEntries(trade.exitIndicators);
            return (
              <tr key={`${trade.code}-${trade.tradeIndex ?? index}`}>
                <td>
                  <div className="product-table__stack">
                    <span className="product-table__mono">{trade.entrySignalDate || trade.entryDate || '--'} → {trade.exitSignalDate || trade.exitDate || '--'}</span>
                    <span>{trade.entryDate || '--'} @ {formatNumber(trade.entryPrice)}</span>
                    <span>{trade.exitDate || '--'} @ {formatNumber(trade.exitPrice)}</span>
                  </div>
                </td>
                <td>{trade.entryTrigger || trade.entrySignal || '--'}</td>
                <td>{trade.exitTrigger || trade.exitSignal || '--'}</td>
                <td>
                  <div className="indicator-stack">
                    {entryIndicators.length > 0 ? (
                      <div>
                        <p className="metric-card__label">Entry</p>
                        <div className="product-chip-list product-chip-list--tight">
                          {entryIndicators.map((item) => (
                            <span key={`entry-${item.key}`} className="product-chip">
                              {item.key}: {item.value}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {exitIndicators.length > 0 ? (
                      <div>
                        <p className="metric-card__label">Exit</p>
                        <div className="product-chip-list product-chip-list--tight">
                          {exitIndicators.map((item) => (
                            <span key={`exit-${item.key}`} className="product-chip">
                              {item.key}: {item.value}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                </td>
                <td className="product-table__align-right">{pct(trade.returnPct)}</td>
                <td className="product-table__align-right">
                  <div className="product-table__stack">
                    <span>{trade.holdingBars ?? trade.holdingDays ?? '--'} bars</span>
                    <span>{trade.holdingCalendarDays ?? '--'} 天</span>
                  </div>
                </td>
                <td>
                  <div className="product-table__stack">
                    <span>信号价口径: {trade.signalPriceBasis || '--'}</span>
                    <span>成交价口径: {trade.priceBasis || '--'}</span>
                    <span>手续费 / 滑点: {formatNumber(trade.feeBps, 1)}bp / {formatNumber(trade.slippageBps, 1)}bp</span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export const RuleRunsTable: React.FC<{
  rows: RuleBacktestHistoryItem[];
  selectedRunId: number | null;
  onOpen: (run: RuleBacktestHistoryItem) => void;
}> = ({ rows, selectedRunId, onOpen }) => {
  if (rows.length === 0) {
    return <div className="product-empty-state">暂无确定性规则回测历史。</div>;
  }

  return (
    <div className="product-table-shell">
      <table className="product-table">
        <thead>
          <tr>
            <th>运行时间</th>
            <th>代码</th>
            <th>状态</th>
            <th className="product-table__align-right">回看范围</th>
            <th className="product-table__align-right">交易</th>
            <th className="product-table__align-right">总收益</th>
            <th className="product-table__align-right">超额收益</th>
            <th className="product-table__align-right">操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} data-active={selectedRunId === row.id ? 'true' : 'false'}>
              <td>{formatDateTime(row.runAt)}</td>
              <td className="product-table__mono">{row.code}</td>
              <td>
                <div className="product-table__stack">
                  {getRuleStatusBadge(row.status)}
                  <span>{row.statusMessage || '--'}</span>
                </div>
              </td>
              <td className="product-table__align-right">{row.lookbackBars}</td>
              <td className="product-table__align-right">{row.tradeCount}</td>
              <td className="product-table__align-right">{pct(row.totalReturnPct)}</td>
              <td className="product-table__align-right">{pct(row.excessReturnVsBuyAndHoldPct)}</td>
              <td className="product-table__align-right">
                <Button size="sm" variant="ghost" onClick={() => onOpen(row)}>
                  查看
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
