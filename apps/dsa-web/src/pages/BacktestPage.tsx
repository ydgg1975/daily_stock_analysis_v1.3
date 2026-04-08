import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { backtestApi } from '../api/backtest';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Badge, Button, Card, Pagination, WorkspacePageHeader } from '../components/common';
import type {
  AssumptionMap,
  BacktestResultItem,
  BacktestRunHistoryItem,
  BacktestRunResponse,
  BacktestSampleStatusResponse,
  PerformanceMetrics,
  PrepareBacktestSamplesResponse,
  RuleBacktestHistoryItem,
  RuleBacktestParseResponse,
  RuleBacktestRunResponse,
  RuleBacktestTradeItem,
} from '../types/backtest';

const HISTORICAL_PAGE_SIZE = 20;
const HISTORY_PAGE_SIZE = 10;
const RULE_HISTORY_PAGE_SIZE = 10;
const RULE_POLL_INTERVAL_MS = 1800;

type ActiveModule = 'historical' | 'rule';

type PerformanceNotice = {
  tone: 'warning' | 'danger';
  message: string;
};

const RULE_STATUS_LABELS: Record<string, string> = {
  parsing: '解析中',
  queued: '排队中',
  running: '运行中',
  summarizing: '整理摘要',
  completed: '已完成',
  failed: '失败',
};

const HISTORICAL_STATUS_LABELS: Record<string, string> = {
  completed: '已完成',
  error: '执行异常',
  insufficient_data: '样本不足',
};

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

function pct(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value.toFixed(2)}%`;
}

function formatNumber(value?: number | null, digits = 2): string {
  if (value == null || Number.isNaN(value)) return '--';
  return value.toFixed(digits);
}

function formatDateTime(value?: string | null): string {
  if (!value) return '--';
  return value.replace('T', ' ').replace('Z', '');
}

function parsePositiveInt(value: string, fallback: number, minimum = 1): number {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(minimum, parsed);
}

function formatAssumptionValue(value: unknown): string {
  if (value == null) return '--';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value)) return value.join(', ');
  return String(value);
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

function isRuleRunTerminal(status?: string): boolean {
  return status === 'completed' || status === 'failed';
}

function getHistoricalStatusBadge(status?: string) {
  const normalized = status || 'completed';
  const label = HISTORICAL_STATUS_LABELS[normalized] || normalized;
  if (normalized === 'completed') return <Badge variant="success">{label}</Badge>;
  if (normalized === 'insufficient_data') return <Badge variant="warning">{label}</Badge>;
  if (normalized === 'error') return <Badge variant="danger">{label}</Badge>;
  return <Badge variant="default">{label}</Badge>;
}

function getRuleStatusBadge(status?: string) {
  const normalized = status || 'queued';
  const label = RULE_STATUS_LABELS[normalized] || normalized;
  if (normalized === 'completed') return <Badge variant="success">{label}</Badge>;
  if (normalized === 'failed') return <Badge variant="danger">{label}</Badge>;
  if (normalized === 'summarizing') return <Badge variant="info">{label}</Badge>;
  if (normalized === 'running') return <Badge variant="warning">{label}</Badge>;
  return <Badge variant="default">{label}</Badge>;
}

function renderDirectionBadge(correct?: boolean | null, expected?: string | null) {
  if (correct === true) return <span className="product-direction product-direction--positive">✓ {expected || '匹配'}</span>;
  if (correct === false) return <span className="product-direction product-direction--negative">✕ {expected || '偏离'}</span>;
  return <span className="product-direction">--</span>;
}

const SectionEyebrow: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span className="product-kicker">{children}</span>
);

const MetricCard: React.FC<{
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

const Banner: React.FC<{
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

const Disclosure: React.FC<{
  summary: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}> = ({ summary, children, defaultOpen = false }) => (
  <details className="product-disclosure" open={defaultOpen}>
    <summary className="product-disclosure__summary">{summary}</summary>
    <div className="product-disclosure__body">{children}</div>
  </details>
);

const AssumptionList: React.FC<{
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

const PerformanceGroup: React.FC<{
  title: string;
  metrics: PerformanceMetrics;
}> = ({ title, metrics }) => (
  <div className="summary-block">
    <div className="summary-block__header">
      <div>
        <SectionEyebrow>{title}</SectionEyebrow>
        <h3 className="summary-block__title">Performance snapshot</h3>
      </div>
      <span className="product-inline-meta">
        {metrics.completedCount}/{metrics.totalEvaluations} 条有效评估
      </span>
    </div>
    <div className="metric-grid metric-grid--compact">
      <MetricCard label="方向准确率" value={pct(metrics.directionAccuracyPct)} tone="accent" />
      <MetricCard label="胜率" value={pct(metrics.winRatePct)} tone="positive" />
      <MetricCard label="平均模拟收益" value={pct(metrics.avgSimulatedReturnPct)} />
      <MetricCard label="平均标的收益" value={pct(metrics.avgStockReturnPct)} />
      <MetricCard label="止损触发率" value={pct(metrics.stopLossTriggerRate)} />
      <MetricCard label="止盈触发率" value={pct(metrics.takeProfitTriggerRate)} />
    </div>
  </div>
);

const HistoricalRunSummary: React.FC<{ data: BacktestRunResponse }> = ({ data }) => (
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

const RuleRunStatusBanner: React.FC<{ run: RuleBacktestRunResponse }> = ({ run }) => {
  const latestStatusAt = run.statusHistory?.[run.statusHistory.length - 1]?.at;
  const tone = run.status === 'failed'
    ? 'danger'
    : run.status === 'completed'
      ? 'success'
      : run.status === 'summarizing'
        ? 'info'
        : 'warning';

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
          {run.statusMessage || '规则回测已提交。'}
          <span className="product-banner__meta">
            运行 #{run.id} · {run.code} · {latestStatusAt ? formatDateTime(latestStatusAt) : '--'}
          </span>
          {run.noResultMessage ? <span className="product-banner__meta">{run.noResultMessage}</span> : null}
        </>
      )}
    />
  );
};

const RuleBacktestChart: React.FC<{ points: RuleBacktestRunResponse['equityCurve'] }> = ({ points }) => {
  const geometry = useMemo(() => {
    if (!points.length) return null;
    const width = 920;
    const height = 260;
    const paddingX = 20;
    const paddingY = 20;
    const equities = points.map((point) => Number(point.equity ?? 0));
    const min = Math.min(...equities);
    const max = Math.max(...equities);
    const span = max - min || 1;
    const usableWidth = width - paddingX * 2;
    const usableHeight = height - paddingY * 2;
    const coords = points.map((point, index) => {
      const x = paddingX + (usableWidth * index) / Math.max(1, points.length - 1);
      const y = paddingY + usableHeight - ((Number(point.equity ?? 0) - min) / span) * usableHeight;
      return `${x},${y}`;
    });
    const first = points[0];
    const last = points[points.length - 1];
    return {
      width,
      height,
      polyline: coords.join(' '),
      min,
      max,
      first,
      last,
    };
  }, [points]);

  if (!geometry) {
    return <div className="product-empty-state product-empty-state--compact">暂无权益曲线数据。</div>;
  }

  return (
    <div className="chart-card">
      <div className="summary-block__header">
        <div>
          <SectionEyebrow>Equity Curve</SectionEyebrow>
          <h3 className="summary-block__title">Deterministic execution path</h3>
        </div>
        <span className="product-inline-meta">{points.length} 个观测点</span>
      </div>
      <div className="chart-card__frame">
        <svg viewBox={`0 0 ${geometry.width} ${geometry.height}`} className="chart-card__svg" aria-label="权益曲线图">
          <line x1="20" y1="20" x2="20" y2="240" className="chart-card__grid" />
          <line x1="20" y1="240" x2="900" y2="240" className="chart-card__grid" />
          <polyline className="chart-card__area" points={`20,240 ${geometry.polyline} 900,240`} />
          <polyline className="chart-card__line" points={geometry.polyline} />
        </svg>
      </div>
      <div className="chart-card__footer">
        <div>
          <p className="metric-card__label">起点</p>
          <p className="chart-card__value">{geometry.first?.date || '--'}</p>
          <p className="metric-card__note">{pct(geometry.first?.cumulativeReturnPct)}</p>
        </div>
        <div>
          <p className="metric-card__label">终点</p>
          <p className="chart-card__value">{geometry.last?.date || '--'}</p>
          <p className="metric-card__note">{pct(geometry.last?.cumulativeReturnPct)}</p>
        </div>
      </div>
    </div>
  );
};

const HistoricalResultsTable: React.FC<{ rows: BacktestResultItem[] }> = ({ rows }) => {
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
            <th>数据源</th>
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

const HistoricalRunsTable: React.FC<{
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

const RuleBacktestTradeTable: React.FC<{ trades: RuleBacktestTradeItem[] }> = ({ trades }) => {
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

const RuleRunsTable: React.FC<{
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
            <th className="product-table__align-right">Lookback</th>
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

const RuleParsedPreview: React.FC<{
  parsed: RuleBacktestParseResponse | null;
  confirmed: boolean;
  onToggleConfirmed: (value: boolean) => void;
}> = ({ parsed, confirmed, onToggleConfirmed }) => {
  if (!parsed) {
    return (
      <div className="product-empty-state product-empty-state--compact">
        先解析自然语言策略，再查看归一化规则、时间周期和最大 lookback。
      </div>
    );
  }

  const needsAttention = parsed.needsConfirmation || parsed.confidence < 0.85 || parsed.ambiguities.length > 0;

  return (
    <div className="summary-block">
      <div className="summary-block__header">
        <div>
          <SectionEyebrow>Parsed Rule</SectionEyebrow>
          <h3 className="summary-block__title">归一化策略预览</h3>
        </div>
        {needsAttention ? <Badge variant="warning">需要确认</Badge> : <Badge variant="success">可运行</Badge>}
      </div>
      <div className="preview-grid">
        <div className="preview-card">
          <p className="metric-card__label">标准化策略</p>
          <p className="preview-card__text">{parsed.parsedStrategy.normalizedText || '--'}</p>
        </div>
        <div className="preview-card">
          <p className="metric-card__label">时间周期 / 最大 lookback</p>
          <p className="preview-card__text">{parsed.parsedStrategy.timeframe || 'daily'} / {parsed.maxLookback} bars</p>
        </div>
        <div className="preview-card">
          <p className="metric-card__label">入场规则</p>
          <p className="preview-card__text">{parsed.summary.entry || '--'}</p>
        </div>
        <div className="preview-card">
          <p className="metric-card__label">离场规则</p>
          <p className="preview-card__text">{parsed.summary.exit || '--'}</p>
        </div>
      </div>
      {parsed.ambiguities.length > 0 ? (
        <Banner
          tone="warning"
          className="mt-4"
          title="解析提示"
          body={(
            <ul className="product-list">
              {parsed.ambiguities.slice(0, 4).map((item, index) => (
                <li key={`${String(item.code || index)}`}>
                  {String(item.message || item.suggestion || '该规则仍需人工确认。')}
                </li>
              ))}
            </ul>
          )}
        />
      ) : null}
      <label className="product-checkbox-row mt-4">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(event) => onToggleConfirmed(event.target.checked)}
        />
        <span>我已确认规则解析结果，允许按显式执行假设运行确定性回测。</span>
      </label>
    </div>
  );
};

const BacktestPage: React.FC = () => {
  useEffect(() => {
    document.title = 'Backtesting - WolfyStock';
  }, []);

  const [activeModule, setActiveModule] = useState<ActiveModule>('historical');
  const [codeFilter, setCodeFilter] = useState('');
  const [evaluationBars, setEvaluationBars] = useState('10');
  const [maturityDays, setMaturityDays] = useState('14');
  const [samplePreset, setSamplePreset] = useState('60');
  const [customSampleCount, setCustomSampleCount] = useState('252');
  const [forceReplaceResults, setForceReplaceResults] = useState(false);

  const [isRunningHistoricalEval, setIsRunningHistoricalEval] = useState(false);
  const [runResult, setRunResult] = useState<BacktestRunResponse | null>(null);
  const [runError, setRunError] = useState<ParsedApiError | null>(null);

  const [prepareResult, setPrepareResult] = useState<PrepareBacktestSamplesResponse | null>(null);
  const [prepareError, setPrepareError] = useState<ParsedApiError | null>(null);
  const [isPreparingSamples, setIsPreparingSamples] = useState(false);

  const [pageError, setPageError] = useState<ParsedApiError | null>(null);
  const [historyError, setHistoryError] = useState<ParsedApiError | null>(null);
  const [sampleStatusError, setSampleStatusError] = useState<ParsedApiError | null>(null);

  const [sampleStatus, setSampleStatus] = useState<BacktestSampleStatusResponse | null>(null);
  const [results, setResults] = useState<BacktestResultItem[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [isLoadingResults, setIsLoadingResults] = useState(false);

  const [historyItems, setHistoryItems] = useState<BacktestRunHistoryItem[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingSampleStatus, setIsLoadingSampleStatus] = useState(false);

  const [overallPerf, setOverallPerf] = useState<PerformanceMetrics | null>(null);
  const [stockPerf, setStockPerf] = useState<PerformanceMetrics | null>(null);
  const [isLoadingPerf, setIsLoadingPerf] = useState(false);
  const [performanceNotice, setPerformanceNotice] = useState<PerformanceNotice | null>(null);

  const [ruleStrategyText, setRuleStrategyText] = useState(
    'Buy when MA5 > MA20 and RSI6 < 40. Sell when MA5 < MA20 or RSI6 > 70.',
  );
  const [ruleLookbackBars, setRuleLookbackBars] = useState('252');
  const [ruleInitialCapital, setRuleInitialCapital] = useState('100000');
  const [ruleFeeBps, setRuleFeeBps] = useState('0');
  const [ruleSlippageBps, setRuleSlippageBps] = useState('0');
  const [ruleParsedStrategy, setRuleParsedStrategy] = useState<RuleBacktestParseResponse | null>(null);
  const [ruleConfirmed, setRuleConfirmed] = useState(false);
  const [isParsingRuleStrategy, setIsParsingRuleStrategy] = useState(false);
  const [ruleParseError, setRuleParseError] = useState<ParsedApiError | null>(null);
  const [ruleRunResult, setRuleRunResult] = useState<RuleBacktestRunResponse | null>(null);
  const [isSubmittingRuleBacktest, setIsSubmittingRuleBacktest] = useState(false);
  const [ruleRunError, setRuleRunError] = useState<ParsedApiError | null>(null);
  const [ruleHistoryItems, setRuleHistoryItems] = useState<RuleBacktestHistoryItem[]>([]);
  const [ruleHistoryTotal, setRuleHistoryTotal] = useState(0);
  const [ruleHistoryPage, setRuleHistoryPage] = useState(1);
  const [isLoadingRuleHistory, setIsLoadingRuleHistory] = useState(false);
  const [ruleHistoryError, setRuleHistoryError] = useState<ParsedApiError | null>(null);
  const [selectedRuleRunId, setSelectedRuleRunId] = useState<number | null>(null);

  const normalizedCode = codeFilter.trim().toUpperCase();
  const resolvedSampleCount = samplePreset === 'custom'
    ? parsePositiveInt(customSampleCount, 252)
    : parsePositiveInt(samplePreset, 60);

  const historicalAssumptions = runResult?.executionAssumptions
    || overallPerf?.executionAssumptions
    || results[0]?.executionAssumptions
    || null;

  const previewRuleAssumptions = useMemo<AssumptionMap>(() => ({
    timeframe: ruleParsedStrategy?.parsedStrategy.timeframe || 'daily',
    price_basis: 'close',
    signal_evaluation_timing: 'bar close',
    entry_fill_timing: 'next bar open',
    exit_fill_timing: 'next bar open; final bar may force close at close',
    position_sizing: '100% capital when long, otherwise cash',
    fee_bps_per_side: Number.parseFloat(ruleFeeBps) || 0,
    slippage_bps_per_side: Number.parseFloat(ruleSlippageBps) || 0,
  }), [ruleFeeBps, ruleParsedStrategy?.parsedStrategy.timeframe, ruleSlippageBps]);

  const applyRuleRunDetail = useCallback((data: RuleBacktestRunResponse) => {
    setRuleRunResult(data);
    setSelectedRuleRunId(data.id);
    setCodeFilter(data.code);
    setRuleStrategyText(data.strategyText);
    setRuleLookbackBars(String(data.lookbackBars || 252));
    setRuleInitialCapital(String(data.initialCapital || 100000));
    setRuleFeeBps(String(data.feeBps ?? 0));
    setRuleSlippageBps(String(data.slippageBps ?? 0));
    const parsedStrategySummary = (data.summary.parsedStrategySummary as Record<string, string> | undefined)
      || data.parsedStrategy.summary;
    setRuleParsedStrategy({
      code: data.code,
      strategyText: data.strategyText,
      parsedStrategy: {
        ...data.parsedStrategy,
        summary: parsedStrategySummary,
      },
      confidence: data.parsedConfidence ?? data.parsedStrategy.confidence ?? 0,
      needsConfirmation: data.needsConfirmation,
      ambiguities: data.warnings,
      summary: parsedStrategySummary,
      maxLookback: data.parsedStrategy.maxLookback,
    });
    setRuleConfirmed(true);
  }, []);

  const fetchResults = useCallback(async (
    page = 1,
    code?: string,
    windowBars?: number,
    runId?: number | null,
  ) => {
    setIsLoadingResults(true);
    try {
      const response = await backtestApi.getResults({
        code: code || undefined,
        evalWindowDays: windowBars,
        runId: runId || undefined,
        page,
        limit: HISTORICAL_PAGE_SIZE,
      });
      setResults(response.items);
      setTotalResults(response.total);
      setCurrentPage(response.page);
      setPageError(null);
    } catch (error) {
      setPageError(getParsedApiError(error));
    } finally {
      setIsLoadingResults(false);
    }
  }, []);

  const fetchHistory = useCallback(async (page = 1, code?: string) => {
    setIsLoadingHistory(true);
    try {
      const response = await backtestApi.getHistory({ code: code || undefined, page, limit: HISTORY_PAGE_SIZE });
      setHistoryItems(response.items);
      setHistoryTotal(response.total);
      setHistoryPage(response.page);
      setHistoryError(null);
    } catch (error) {
      setHistoryError(getParsedApiError(error));
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  const fetchSampleStatus = useCallback(async (code?: string) => {
    if (!code) {
      setSampleStatus(null);
      setSampleStatusError(null);
      return;
    }
    setIsLoadingSampleStatus(true);
    try {
      const response = await backtestApi.getSampleStatus(code);
      setSampleStatus(response);
      setSampleStatusError(null);
    } catch (error) {
      setSampleStatus(null);
      setSampleStatusError(getParsedApiError(error));
    } finally {
      setIsLoadingSampleStatus(false);
    }
  }, []);

  const fetchRuleHistory = useCallback(async (page = 1, code?: string) => {
    setIsLoadingRuleHistory(true);
    try {
      const response = await backtestApi.getRuleBacktestRuns({ code: code || undefined, page, limit: RULE_HISTORY_PAGE_SIZE });
      setRuleHistoryItems(response.items);
      setRuleHistoryTotal(response.total);
      setRuleHistoryPage(response.page);
      setRuleHistoryError(null);
    } catch (error) {
      setRuleHistoryError(getParsedApiError(error));
    } finally {
      setIsLoadingRuleHistory(false);
    }
  }, []);

  const fetchPerformance = useCallback(async (
    code?: string,
    windowBars?: number,
    options: { showNotice?: boolean } = {},
  ) => {
    const { showNotice = true } = options;
    setIsLoadingPerf(true);
    const notices: string[] = [];
    let hasDanger = false;

    try {
      const overall = await backtestApi.getOverallPerformance(windowBars);
      setOverallPerf(overall);
      if (overall == null && showNotice) notices.push('暂无整体历史分析评估汇总。');
    } catch (error) {
      setOverallPerf(null);
      hasDanger = true;
      if (showNotice) notices.push(getParsedApiError(error).message);
    }

    if (code) {
      try {
        const stock = await backtestApi.getStockPerformance(code, windowBars);
        setStockPerf(stock);
        if (stock == null && showNotice) notices.push(`暂无 ${code} 的单股历史分析评估汇总。`);
      } catch (error) {
        setStockPerf(null);
        hasDanger = true;
        if (showNotice) notices.push(getParsedApiError(error).message);
      }
    } else {
      setStockPerf(null);
    }

    if (showNotice && notices.length > 0) {
      setPerformanceNotice({
        tone: hasDanger ? 'danger' : 'warning',
        message: notices.join(' '),
      });
    } else if (showNotice) {
      setPerformanceNotice(null);
    }

    setIsLoadingPerf(false);
  }, []);

  useEffect(() => {
    const init = async () => {
      try {
        const overall = await backtestApi.getOverallPerformance();
        setOverallPerf(overall);
        const defaultWindow = overall?.evalWindowDays;
        if (defaultWindow) setEvaluationBars(String(defaultWindow));
        setPerformanceNotice(null);
      } catch (error) {
        setPerformanceNotice({
          tone: 'danger',
          message: getParsedApiError(error).message,
        });
      } finally {
        void fetchResults(1, undefined, undefined, null);
        void fetchHistory(1, undefined);
        void fetchRuleHistory(1, undefined);
      }
    };
    void init();
  }, [fetchHistory, fetchResults, fetchRuleHistory]);

  useEffect(() => {
    if (!ruleRunResult?.id || isRuleRunTerminal(ruleRunResult.status)) return undefined;

    let cancelled = false;
    let timer: number | undefined;

    const poll = async () => {
      try {
        const detail = await backtestApi.getRuleBacktestRun(ruleRunResult.id);
        if (cancelled) return;
        applyRuleRunDetail(detail);
        if (isRuleRunTerminal(detail.status)) {
          await fetchRuleHistory(1, detail.code || undefined);
          return;
        }
      } catch (error) {
        if (!cancelled) setRuleRunError(getParsedApiError(error));
      }
      if (!cancelled) timer = window.setTimeout(() => void poll(), RULE_POLL_INTERVAL_MS);
    };

    timer = window.setTimeout(() => void poll(), RULE_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [applyRuleRunDetail, fetchRuleHistory, ruleRunResult?.id, ruleRunResult?.status]);

  const handleFilter = () => {
    const code = normalizedCode || undefined;
    const windowBars = parsePositiveInt(evaluationBars, 10);
    setSelectedRunId(null);
    setHistoryPage(1);
    setCurrentPage(1);
    setRuleHistoryPage(1);
    setPerformanceNotice(null);
    if (ruleRunResult && code && ruleRunResult.code !== code) {
      setRuleRunResult(null);
      setSelectedRuleRunId(null);
    }
    void fetchResults(1, code, windowBars, null);
    void fetchHistory(1, code);
    void fetchSampleStatus(code);
    void fetchPerformance(code, windowBars, { showNotice: true });
    void fetchRuleHistory(1, code);
  };

  const handleRunHistoricalEvaluation = async () => {
    setIsRunningHistoricalEval(true);
    setRunResult(null);
    setRunError(null);
    setPrepareResult(null);
    setPrepareError(null);
    try {
      const windowBars = parsePositiveInt(evaluationBars, 10);
      const maturityCalendarDays = parsePositiveInt(maturityDays, 14, 0);
      const response = await backtestApi.run({
        code: normalizedCode || undefined,
        force: forceReplaceResults,
        evalWindowDays: windowBars,
        minAgeDays: maturityCalendarDays,
      });
      setRunResult(response);
      setSelectedRunId(response.runId ?? null);
      await Promise.all([
        fetchResults(1, normalizedCode || undefined, windowBars, response.runId ?? null),
        fetchHistory(1, normalizedCode || undefined),
        fetchSampleStatus(normalizedCode || undefined),
      ]);
      await fetchPerformance(normalizedCode || undefined, windowBars, { showNotice: true });
    } catch (error) {
      setRunError(getParsedApiError(error));
    } finally {
      setIsRunningHistoricalEval(false);
    }
  };

  const handlePrepareSamples = async (options: { forceRefresh?: boolean } = {}) => {
    if (!normalizedCode) {
      setPrepareError({
        title: '缺少股票代码',
        message: '请先输入股票代码，再准备历史分析评估样本。',
        rawMessage: '请先输入股票代码，再准备历史分析评估样本。',
        category: 'missing_params',
      });
      return;
    }

    setIsPreparingSamples(true);
    setPrepareResult(null);
    setPrepareError(null);
    try {
      const response = await backtestApi.prepareSamples({
        code: normalizedCode,
        sampleCount: resolvedSampleCount,
        evalWindowDays: parsePositiveInt(evaluationBars, 10),
        minAgeDays: parsePositiveInt(maturityDays, 14, 0),
        forceRefresh: options.forceRefresh || false,
      });
      setPrepareResult(response);
      await Promise.all([
        fetchSampleStatus(normalizedCode),
        fetchHistory(1, normalizedCode),
      ]);
    } catch (error) {
      setPrepareError(getParsedApiError(error));
    } finally {
      setIsPreparingSamples(false);
    }
  };

  const handleRebuildSamples = async () => {
    if (!normalizedCode) {
      setPrepareError({
        title: '缺少股票代码',
        message: '请先输入股票代码，再重建历史分析评估样本。',
        rawMessage: '请先输入股票代码，再重建历史分析评估样本。',
        category: 'missing_params',
      });
      return;
    }

    setIsPreparingSamples(true);
    setPrepareResult(null);
    setPrepareError(null);
    try {
      await backtestApi.clearSamples(normalizedCode);
      await handlePrepareSamples({ forceRefresh: false });
      await fetchResults(1, normalizedCode, parsePositiveInt(evaluationBars, 10), null);
    } catch (error) {
      setPrepareError(getParsedApiError(error));
      setIsPreparingSamples(false);
    }
  };

  const handleClearSamples = async () => {
    if (!normalizedCode) {
      setPrepareError({
        title: '缺少股票代码',
        message: '请先输入股票代码，再清理历史分析评估样本。',
        rawMessage: '请先输入股票代码，再清理历史分析评估样本。',
        category: 'missing_params',
      });
      return;
    }

    setIsPreparingSamples(true);
    setPrepareError(null);
    try {
      await backtestApi.clearSamples(normalizedCode);
      setPrepareResult(null);
      setRunResult(null);
      setSelectedRunId(null);
      setResults([]);
      setTotalResults(0);
      setOverallPerf(null);
      setStockPerf(null);
      await Promise.all([
        fetchSampleStatus(normalizedCode),
        fetchHistory(1, normalizedCode),
        fetchResults(1, normalizedCode, parsePositiveInt(evaluationBars, 10), null),
      ]);
      await fetchPerformance(normalizedCode, parsePositiveInt(evaluationBars, 10), { showNotice: true });
    } catch (error) {
      setPrepareError(getParsedApiError(error));
    } finally {
      setIsPreparingSamples(false);
    }
  };

  const handleClearResults = async () => {
    if (!normalizedCode) {
      setRunError({
        title: '缺少股票代码',
        message: '请先输入股票代码，再清理历史分析评估结果。',
        rawMessage: '请先输入股票代码，再清理历史分析评估结果。',
        category: 'missing_params',
      });
      return;
    }

    setIsRunningHistoricalEval(true);
    setRunError(null);
    try {
      await backtestApi.clearResults(normalizedCode);
      setRunResult(null);
      setSelectedRunId(null);
      setResults([]);
      setTotalResults(0);
      await Promise.all([
        fetchHistory(1, normalizedCode),
        fetchResults(1, normalizedCode, parsePositiveInt(evaluationBars, 10), null),
      ]);
      await fetchPerformance(normalizedCode, parsePositiveInt(evaluationBars, 10), { showNotice: true });
    } catch (error) {
      setRunError(getParsedApiError(error));
    } finally {
      setIsRunningHistoricalEval(false);
    }
  };

  const handleOpenHistoricalRun = async (run: BacktestRunHistoryItem) => {
    setSelectedRunId(run.id);
    setCodeFilter(run.code || '');
    setEvaluationBars(String(run.evaluationWindowTradingBars || run.evalWindowDays));
    setMaturityDays(String(run.maturityCalendarDays || run.minAgeDays));
    setForceReplaceResults(false);
    setPerformanceNotice(null);
    await Promise.all([
      fetchHistory(1, run.code || undefined),
      fetchSampleStatus(run.code || undefined),
      fetchResults(1, run.code || undefined, run.evalWindowDays, run.id),
    ]);
    await fetchPerformance(run.code || undefined, run.evalWindowDays, { showNotice: true });
  };

  const handleParseRuleStrategy = async () => {
    if (!normalizedCode) {
      setRuleParseError({
        title: '缺少股票代码',
        message: '请先输入股票代码，再解析规则文本。',
        rawMessage: '请先输入股票代码，再解析规则文本。',
        category: 'missing_params',
      });
      return;
    }

    if (!ruleStrategyText.trim()) {
      setRuleParseError({
        title: '缺少策略文本',
        message: '请输入规则策略文本后再解析。',
        rawMessage: '请输入规则策略文本后再解析。',
        category: 'missing_params',
      });
      return;
    }

    setIsParsingRuleStrategy(true);
    setRuleParseError(null);
    setRuleRunError(null);
    try {
      const response = await backtestApi.parseRuleStrategy({
        code: normalizedCode,
        strategyText: ruleStrategyText,
      });
      setRuleParsedStrategy(response);
      setRuleConfirmed(false);
      setRuleRunResult(null);
      setSelectedRuleRunId(null);
      await fetchRuleHistory(1, normalizedCode);
    } catch (error) {
      setRuleParseError(getParsedApiError(error));
    } finally {
      setIsParsingRuleStrategy(false);
    }
  };

  const handleRunRuleBacktest = async () => {
    if (!normalizedCode) {
      setRuleRunError({
        title: '缺少股票代码',
        message: '请输入股票代码后再提交规则回测。',
        rawMessage: '请输入股票代码后再提交规则回测。',
        category: 'missing_params',
      });
      return;
    }
    if (!ruleParsedStrategy) {
      setRuleRunError({
        title: '需要先解析策略',
        message: '请先解析并确认规则结构，再提交确定性规则回测。',
        rawMessage: '请先解析并确认规则结构，再提交确定性规则回测。',
        category: 'validation_error',
      });
      return;
    }
    if (!ruleConfirmed) {
      setRuleRunError({
        title: '需要确认解析结果',
        message: '请确认归一化规则后再提交回测。',
        rawMessage: '请确认归一化规则后再提交回测。',
        category: 'validation_error',
      });
      return;
    }

    setIsSubmittingRuleBacktest(true);
    setRuleRunError(null);
    try {
      const response = await backtestApi.runRuleBacktest({
        code: normalizedCode,
        strategyText: ruleStrategyText,
        parsedStrategy: ruleParsedStrategy.parsedStrategy,
        lookbackBars: parsePositiveInt(ruleLookbackBars, 252, 10),
        initialCapital: Number.parseFloat(ruleInitialCapital) || 100000,
        feeBps: Number.parseFloat(ruleFeeBps) || 0,
        slippageBps: Number.parseFloat(ruleSlippageBps) || 0,
        confirmed: true,
        waitForCompletion: false,
      });
      applyRuleRunDetail(response);
      setActiveModule('rule');
      await fetchRuleHistory(1, normalizedCode);
    } catch (error) {
      setRuleRunError(getParsedApiError(error));
    } finally {
      setIsSubmittingRuleBacktest(false);
    }
  };

  const handleOpenRuleRun = async (run: RuleBacktestHistoryItem) => {
    setSelectedRuleRunId(run.id);
    setCodeFilter(run.code);
    setRuleConfirmed(true);
    setRuleRunError(null);
    try {
      const detail = await backtestApi.getRuleBacktestRun(run.id);
      applyRuleRunDetail(detail);
      setActiveModule('rule');
    } catch (error) {
      setRuleRunError(getParsedApiError(error));
    }
  };

  const handleResultsPageChange = (page: number) => {
    void fetchResults(
      page,
      normalizedCode || undefined,
      parsePositiveInt(evaluationBars, 10),
      selectedRunId,
    );
  };

  const handleCodeKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') handleFilter();
  };

  return (
    <div className="workspace-page workspace-page--backtest">
      <WorkspacePageHeader
        eyebrow="WolfyStock Quant Lab"
        title="Backtesting"
        description="在同一个量化工作台中区分历史分析评估与确定性规则回测，并把关键语义、执行假设和审计信息放在更克制的层级里。"
      >
        <Card className="product-command-card" padding="md">
          <div className="product-command-row">
            <label className="product-field product-field--grow">
              <span className="theme-field-label">股票代码</span>
              <input
                type="text"
                value={codeFilter}
                onChange={(event) => setCodeFilter(event.target.value.toUpperCase())}
                onKeyDown={handleCodeKeyDown}
                placeholder="输入股票代码，如 AAPL 或 600519"
                className="input-surface input-focus-glow product-command-input"
                aria-label="股票代码"
              />
            </label>
            <Button onClick={handleFilter}>应用筛选</Button>
          </div>
          <div className="product-chip-list">
            <span className="product-chip">当前标的: {normalizedCode || '全部股票'}</span>
            <span className="product-chip">Historical = signal evaluation</span>
            <span className="product-chip">Rule = deterministic execution</span>
          </div>
          <div className="product-module-switch" role="tablist" aria-label="回测模块">
            <button
              type="button"
              role="tab"
              aria-selected={activeModule === 'historical'}
              className={`product-module-switch__button${activeModule === 'historical' ? ' is-active' : ''}`}
              onClick={() => setActiveModule('historical')}
            >
              <span>Historical Analysis Evaluation</span>
              <small>历史分析信号评估</small>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeModule === 'rule'}
              className={`product-module-switch__button${activeModule === 'rule' ? ' is-active' : ''}`}
              onClick={() => setActiveModule('rule')}
            >
              <span>Deterministic Rule Strategy Backtest</span>
              <small>确定性规则回测</small>
            </button>
          </div>
        </Card>
      </WorkspacePageHeader>

      {activeModule === 'historical' ? (
        <>
          <Card
            title="Historical Analysis Evaluation"
            subtitle="Module A"
            className="product-section-card"
          >
            <p className="product-section-copy">
              评估历史 AI 分析样本在后续行情中的方向与收益表现，不把它误读成逐 bar 的交易策略回测。
            </p>
            <div className="product-field-grid">
              <label className="product-field">
                <span className="theme-field-label">评估窗口</span>
                <input
                  type="number"
                  min={1}
                  max={120}
                  value={evaluationBars}
                  onChange={(event) => setEvaluationBars(event.target.value)}
                  className="input-surface input-focus-glow product-command-input"
                  aria-label="评估窗口"
                />
                <span className="product-field-help">单位是 trading bars，例如 10 = 从分析日往后评估 10 根日线。</span>
              </label>
              <label className="product-field">
                <span className="theme-field-label">成熟期</span>
                <input
                  type="number"
                  min={0}
                  max={365}
                  value={maturityDays}
                  onChange={(event) => setMaturityDays(event.target.value)}
                  className="input-surface input-focus-glow product-command-input"
                  aria-label="成熟期"
                />
                <span className="product-field-help">单位是 calendar days，例如 14 = 仅评估 14 天前的分析记录。</span>
              </label>
              <label className="product-field">
                <span className="theme-field-label">分析样本数</span>
                <div className="product-inline-fields">
                  <select
                    value={samplePreset}
                    onChange={(event) => setSamplePreset(event.target.value)}
                    className="input-surface product-command-input"
                    aria-label="分析样本数"
                  >
                    <option value="20">20</option>
                    <option value="60">60</option>
                    <option value="120">120</option>
                    <option value="252">252</option>
                    <option value="custom">自定义</option>
                  </select>
                  {samplePreset === 'custom' ? (
                    <input
                      type="number"
                      min={1}
                      max={365}
                      value={customSampleCount}
                      onChange={(event) => setCustomSampleCount(event.target.value)}
                      className="input-surface input-focus-glow product-command-input"
                      aria-label="自定义样本数"
                    />
                  ) : null}
                </div>
                <span className="product-field-help">表示要准备多少条 analysis samples，而不是天数。</span>
              </label>
            </div>

            <label className="product-checkbox-row">
              <input
                type="checkbox"
                checked={forceReplaceResults}
                onChange={(event) => setForceReplaceResults(event.target.checked)}
                aria-label="覆盖已有同窗口结果"
              />
              <span>覆盖已有同窗口结果。这个开关只影响是否重算，不会改变窗口或成熟期定义。</span>
            </label>

            <div className="product-action-row">
              <Button onClick={() => void handleRunHistoricalEvaluation()} isLoading={isRunningHistoricalEval} loadingText="运行中…">
                运行历史评估
              </Button>
              <Button variant="secondary" onClick={() => void handlePrepareSamples({ forceRefresh: false })} isLoading={isPreparingSamples} disabled={!normalizedCode} loadingText="准备中…">
                准备分析样本
              </Button>
              <Button variant="outline" onClick={() => void handleRebuildSamples()} disabled={isPreparingSamples || !normalizedCode}>
                重建样本
              </Button>
              <Button variant="ghost" onClick={() => void handleClearSamples()} disabled={isPreparingSamples || !normalizedCode}>
                清理样本
              </Button>
              <Button variant="ghost" onClick={() => void handleClearResults()} disabled={isRunningHistoricalEval || !normalizedCode}>
                清理结果
              </Button>
            </div>

            <div className="product-chip-list">
              <span className="product-chip">Window: {parsePositiveInt(evaluationBars, 10)} trading bars</span>
              <span className="product-chip">Maturity: {parsePositiveInt(maturityDays, 14, 0)} calendar days</span>
              <span className="product-chip">Sample size: {resolvedSampleCount} analyses</span>
            </div>

            {runResult ? <HistoricalRunSummary data={runResult} /> : null}
            {prepareResult ? (
              <Banner
                tone="success"
                title="样本准备完成"
                body={(
                  <>
                    新增 {prepareResult.prepared} 条样本，跳过 {prepareResult.skippedExisting} 条已有样本。
                    {prepareResult.noResultMessage ? <span className="product-banner__meta">{prepareResult.noResultMessage}</span> : null}
                  </>
                )}
                className="mt-4"
              />
            ) : null}
            {prepareError ? <ApiErrorAlert error={prepareError} className="mt-4" /> : null}
            {runError ? <ApiErrorAlert error={runError} className="mt-4" /> : null}
          </Card>

          <Card title="Sample Status & Performance" subtitle="Summary" className="product-section-card">
            <div className="summary-split">
              <div className="summary-block">
                <div className="summary-block__header">
                  <div>
                    <SectionEyebrow>Prepared Samples</SectionEyebrow>
                    <h3 className="summary-block__title">样本状态</h3>
                  </div>
                  {isLoadingSampleStatus ? <span className="product-inline-meta">加载中…</span> : null}
                </div>
                <div className="metric-grid metric-grid--compact">
                  <MetricCard label="已准备样本" value={String(sampleStatus?.preparedCount ?? '--')} />
                  <MetricCard
                    label="覆盖日期"
                    value={sampleStatus?.preparedStartDate && sampleStatus?.preparedEndDate ? `${sampleStatus.preparedStartDate} ~ ${sampleStatus.preparedEndDate}` : '--'}
                  />
                  <MetricCard label="评估窗口" value={`${sampleStatus?.evaluationWindowTradingBars || parsePositiveInt(evaluationBars, 10)} bars`} />
                  <MetricCard label="成熟期" value={`${sampleStatus?.maturityCalendarDays || parsePositiveInt(maturityDays, 14, 0)} 天`} />
                </div>
                {sampleStatusError ? <ApiErrorAlert error={sampleStatusError} className="mt-4" /> : null}
              </div>

              <div className="summary-block">
                <div className="summary-block__header">
                  <div>
                    <SectionEyebrow>Performance</SectionEyebrow>
                    <h3 className="summary-block__title">表现汇总</h3>
                  </div>
                  {isLoadingPerf ? <span className="product-inline-meta">加载中…</span> : null}
                </div>
                {performanceNotice ? (
                  <Banner tone={performanceNotice.tone} title={performanceNotice.tone === 'danger' ? '表现数据加载失败' : '表现汇总尚未生成'} body={performanceNotice.message} />
                ) : null}
                {!isLoadingPerf && overallPerf ? <PerformanceGroup title="Overall" metrics={overallPerf} /> : null}
                {!isLoadingPerf && stockPerf ? (
                  <div className="mt-4">
                    <PerformanceGroup title={stockPerf.code || normalizedCode || 'Symbol'} metrics={stockPerf} />
                  </div>
                ) : null}
                {!isLoadingPerf && !overallPerf && !stockPerf && !performanceNotice ? (
                  <div className="product-empty-state product-empty-state--compact">暂无表现汇总。</div>
                ) : null}
              </div>
            </div>

            <Disclosure summary="执行假设与语义说明">
              <AssumptionList
                assumptions={historicalAssumptions || undefined}
                emptyText="运行一次历史分析评估后，这里会显示固定执行假设。"
              />
            </Disclosure>
          </Card>

          <Card
            title={selectedRunId ? `Evaluation Results #${selectedRunId}` : 'Evaluation Results'}
            subtitle="Results"
            className="product-section-card"
          >
            <p className="product-section-copy">
              展示分析建议在后续窗口内的表现、数据源和状态，不把它描述成策略逐笔交易结果。
            </p>
            {pageError ? <ApiErrorAlert error={pageError} className="mb-4" /> : null}
            {isLoadingResults ? (
              <div className="product-empty-state">正在加载历史分析评估结果…</div>
            ) : (
              <HistoricalResultsTable rows={results} />
            )}
            <Pagination
              className="mt-5"
              currentPage={currentPage}
              totalPages={Math.max(1, Math.ceil(totalResults / HISTORICAL_PAGE_SIZE))}
              onPageChange={handleResultsPageChange}
            />
            <p className="product-footnote">共 {totalResults} 条历史分析评估结果。</p>
          </Card>

          <Card title="Run History" subtitle="Historical Module" className="product-section-card">
            {historyError ? <ApiErrorAlert error={historyError} className="mb-4" /> : null}
            {isLoadingHistory ? (
              <div className="product-empty-state">正在加载历史分析评估运行记录…</div>
            ) : (
              <HistoricalRunsTable rows={historyItems} selectedRunId={selectedRunId} onOpen={(run) => void handleOpenHistoricalRun(run)} />
            )}
            <Pagination
              className="mt-5"
              currentPage={historyPage}
              totalPages={Math.max(1, Math.ceil(historyTotal / HISTORY_PAGE_SIZE))}
              onPageChange={(page) => {
                setHistoryPage(page);
                void fetchHistory(page, normalizedCode || undefined);
              }}
            />
            <p className="product-footnote">共 {historyTotal} 条历史分析评估运行记录。</p>
          </Card>
        </>
      ) : (
        <>
          <Card
            title="Deterministic Rule Strategy Backtest"
            subtitle="Module B"
            className="product-section-card"
          >
            <p className="product-section-copy">
              先把自然语言规则解析成标准化 entry / exit 结构，再按显式的价格口径、成交时点、费用和滑点假设执行。
            </p>
            <div className="product-field-grid product-field-grid--rule">
              <label className="product-field product-field--full">
                <span className="theme-field-label">策略文本</span>
                <textarea
                  value={ruleStrategyText}
                  onChange={(event) => setRuleStrategyText(event.target.value)}
                  rows={6}
                  className="input-surface input-focus-glow product-command-input product-command-input--textarea"
                  placeholder="例如：Buy when MA5 > MA20 and RSI6 < 40. Sell when MA5 < MA20 or RSI6 > 70."
                />
                <span className="product-field-help">这里描述的是规则逻辑；真正的成交假设在结果卡与执行假设中显式展示。</span>
              </label>
              <label className="product-field">
                <span className="theme-field-label">Lookback</span>
                <input
                  type="number"
                  min={10}
                  max={5000}
                  value={ruleLookbackBars}
                  onChange={(event) => setRuleLookbackBars(event.target.value)}
                  className="input-surface input-focus-glow product-command-input"
                  aria-label="Lookback"
                />
                <span className="product-field-help">单位是 trading bars，例如 252 = 最近 252 根日线。</span>
              </label>
              <label className="product-field">
                <span className="theme-field-label">初始资金</span>
                <input
                  type="number"
                  min={1}
                  value={ruleInitialCapital}
                  onChange={(event) => setRuleInitialCapital(event.target.value)}
                  className="input-surface input-focus-glow product-command-input"
                  aria-label="初始资金"
                />
              </label>
              <label className="product-field">
                <span className="theme-field-label">单边手续费 (bp)</span>
                <input
                  type="number"
                  min={0}
                  max={500}
                  value={ruleFeeBps}
                  onChange={(event) => setRuleFeeBps(event.target.value)}
                  className="input-surface input-focus-glow product-command-input"
                  aria-label="单边手续费 (bp)"
                />
              </label>
              <label className="product-field">
                <span className="theme-field-label">单边滑点 (bp)</span>
                <input
                  type="number"
                  min={0}
                  max={500}
                  value={ruleSlippageBps}
                  onChange={(event) => setRuleSlippageBps(event.target.value)}
                  className="input-surface input-focus-glow product-command-input"
                  aria-label="单边滑点 (bp)"
                />
              </label>
            </div>

            <div className="product-action-row">
              <Button variant="secondary" onClick={() => void handleParseRuleStrategy()} isLoading={isParsingRuleStrategy} disabled={isSubmittingRuleBacktest || !normalizedCode} loadingText="解析中…">
                解析规则
              </Button>
              <Button onClick={() => void handleRunRuleBacktest()} isLoading={isSubmittingRuleBacktest} disabled={isParsingRuleStrategy || !normalizedCode || !ruleParsedStrategy || !ruleConfirmed} loadingText="提交中…">
                提交规则回测
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setRuleParsedStrategy(null);
                  setRuleConfirmed(false);
                  setRuleRunResult(null);
                  setRuleRunError(null);
                  setRuleParseError(null);
                }}
              >
                重置
              </Button>
            </div>

            <div className="product-chip-list">
              <span className="product-chip">Timeframe: {ruleParsedStrategy?.parsedStrategy.timeframe || 'daily'}</span>
              <span className="product-chip">Price basis: close</span>
              <span className="product-chip">Fill: next bar open</span>
              <span className="product-chip">Fees/slippage: {Number.parseFloat(ruleFeeBps) || 0} / {Number.parseFloat(ruleSlippageBps) || 0} bp</span>
            </div>

            {ruleParseError ? <ApiErrorAlert error={ruleParseError} className="mt-4" /> : null}
            {ruleRunError ? <ApiErrorAlert error={ruleRunError} className="mt-4" /> : null}

            <div className="mt-4">
              <RuleParsedPreview parsed={ruleParsedStrategy} confirmed={ruleConfirmed} onToggleConfirmed={setRuleConfirmed} />
            </div>

            <Disclosure summary="查看提交前执行假设">
              <AssumptionList
                assumptions={previewRuleAssumptions}
                emptyText="填写参数后，这里会显示提交前的默认执行假设。"
              />
            </Disclosure>
          </Card>

          <Card title="Execution Result" subtitle="Rule Run" className="product-section-card">
            {ruleRunResult ? (
              <div className="result-stack">
                <RuleRunStatusBanner run={ruleRunResult} />
                <div className="metric-grid">
                  <MetricCard label="总收益" value={pct(ruleRunResult.totalReturnPct)} tone="accent" />
                  <MetricCard label="Buy & Hold" value={pct(ruleRunResult.buyAndHoldReturnPct)} />
                  <MetricCard
                    label="超额收益"
                    value={pct(ruleRunResult.excessReturnVsBuyAndHoldPct)}
                    tone={(ruleRunResult.excessReturnVsBuyAndHoldPct || 0) >= 0 ? 'positive' : 'negative'}
                  />
                  <MetricCard label="交易次数" value={String(ruleRunResult.tradeCount)} />
                  <MetricCard label="胜率" value={pct(ruleRunResult.winRatePct)} tone="positive" />
                  <MetricCard label="平均单笔收益" value={pct(ruleRunResult.avgTradeReturnPct)} />
                  <MetricCard label="最大回撤" value={pct(ruleRunResult.maxDrawdownPct)} tone="negative" />
                  <MetricCard
                    label="平均持有"
                    value={ruleRunResult.avgHoldingBars != null ? `${ruleRunResult.avgHoldingBars.toFixed(1)} bars` : '--'}
                    note={ruleRunResult.avgHoldingCalendarDays != null ? `${ruleRunResult.avgHoldingCalendarDays.toFixed(1)} 天` : undefined}
                  />
                  <MetricCard label="最终权益" value={formatNumber(ruleRunResult.finalEquity)} />
                </div>

                <div className="summary-split">
                  <RuleBacktestChart points={ruleRunResult.equityCurve || []} />
                  <div className="summary-block">
                    <div className="summary-block__header">
                      <div>
                        <SectionEyebrow>AI Summary</SectionEyebrow>
                        <h3 className="summary-block__title">结果摘要</h3>
                      </div>
                    </div>
                    <p className="product-section-copy">{ruleRunResult.aiSummary || '暂无 AI 摘要。'}</p>
                    <div className="preview-grid mt-4">
                      <div className="preview-card">
                        <p className="metric-card__label">标准化文本</p>
                        <p className="preview-card__text">{ruleRunResult.parsedStrategy.normalizedText || '--'}</p>
                      </div>
                      <div className="preview-card">
                        <p className="metric-card__label">入场规则</p>
                        <p className="preview-card__text">{ruleRunResult.parsedStrategy.summary?.entry || '--'}</p>
                      </div>
                      <div className="preview-card">
                        <p className="metric-card__label">离场规则</p>
                        <p className="preview-card__text">{ruleRunResult.parsedStrategy.summary?.exit || '--'}</p>
                      </div>
                      <div className="preview-card">
                        <p className="metric-card__label">时间周期 / 最大 lookback</p>
                        <p className="preview-card__text">{ruleRunResult.timeframe} / {ruleRunResult.parsedStrategy.maxLookback} bars</p>
                      </div>
                    </div>
                  </div>
                </div>

                <Disclosure summary="执行假设与审计字段" defaultOpen={false}>
                  <AssumptionList
                    assumptions={ruleRunResult.executionAssumptions}
                    emptyText="暂无执行假设。"
                  />
                </Disclosure>

                <div className="summary-block">
                  <div className="summary-block__header">
                    <div>
                      <SectionEyebrow>Trade Audit</SectionEyebrow>
                      <h3 className="summary-block__title">交易明细</h3>
                    </div>
                    <span className="product-inline-meta">{ruleRunResult.trades.length} 笔</span>
                  </div>
                  <RuleBacktestTradeTable trades={ruleRunResult.trades || []} />
                </div>
              </div>
            ) : (
              <div className="product-empty-state">
                解析并提交规则回测后，这里会显示状态、基准比较、权益曲线和交易审计。
              </div>
            )}
          </Card>

          <Card title="Run History" subtitle="Rule Module" className="product-section-card">
            <div className="summary-block__header">
              <div>
                <SectionEyebrow>Async Runs</SectionEyebrow>
                <h3 className="summary-block__title">规则回测历史</h3>
              </div>
              <Button variant="ghost" size="sm" onClick={() => void fetchRuleHistory(1, normalizedCode || undefined)} disabled={isLoadingRuleHistory}>
                {isLoadingRuleHistory ? '刷新中…' : '刷新历史'}
              </Button>
            </div>
            {ruleHistoryError ? <ApiErrorAlert error={ruleHistoryError} className="mb-4" /> : null}
            <RuleRunsTable rows={ruleHistoryItems} selectedRunId={selectedRuleRunId} onOpen={(run) => void handleOpenRuleRun(run)} />
            <Pagination
              className="mt-5"
              currentPage={ruleHistoryPage}
              totalPages={Math.max(1, Math.ceil(ruleHistoryTotal / RULE_HISTORY_PAGE_SIZE))}
              onPageChange={(page) => {
                setRuleHistoryPage(page);
                void fetchRuleHistory(page, normalizedCode || undefined);
              }}
            />
            <p className="product-footnote">共 {ruleHistoryTotal} 条确定性规则回测记录。</p>
          </Card>
        </>
      )}
    </div>
  );
};

export default BacktestPage;
