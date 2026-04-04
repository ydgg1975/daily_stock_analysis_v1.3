import type React from 'react';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { backtestApi } from '../api/backtest';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Card, Badge, Pagination, WorkspacePageHeader } from '../components/common';
import type {
  BacktestResultItem,
  BacktestRunHistoryItem,
  BacktestRunResponse,
  PerformanceMetrics,
  PrepareBacktestSamplesResponse,
  BacktestSampleStatusResponse,
  RuleBacktestParseResponse,
  RuleBacktestRunResponse,
  RuleBacktestHistoryItem,
} from '../types/backtest';

// ============ Helpers ============

function pct(value?: number | null): string {
  if (value == null) return '--';
  return `${value.toFixed(1)}%`;
}

function outcomeBadge(outcome?: string) {
  if (!outcome) return <Badge variant="default">--</Badge>;
  switch (outcome) {
    case 'win':
      return <Badge variant="success" glow>命中</Badge>;
    case 'loss':
      return <Badge variant="danger" glow>失误</Badge>;
    case 'neutral':
      return <Badge variant="warning">中性</Badge>;
    default:
      return <Badge variant="default">{outcome}</Badge>;
  }
}

function statusBadge(status: string) {
  switch (status) {
    case 'completed':
      return <Badge variant="success">完成</Badge>;
    case 'insufficient':
      return <Badge variant="warning">样本不足</Badge>;
    case 'error':
      return <Badge variant="danger">异常</Badge>;
    default:
      return <Badge variant="default">{status}</Badge>;
  }
}

function boolIcon(value?: boolean | null) {
  if (value === true) return <span className="text-success">&#10003;</span>;
  if (value === false) return <span className="text-danger">&#10007;</span>;
  return <span className="text-muted-text">--</span>;
}

type PerformanceNotice = {
  tone: 'warning' | 'danger';
  message: string;
};

// ============ Metric Row ============

const MetricRow: React.FC<{ label: string; value: string; accent?: boolean }> = ({ label, value, accent }) => (
  <div className="flex items-center justify-between border-b border-white/5 py-1.5 last:border-0">
    <span className="text-xs text-secondary-text">{label}</span>
    <span className={`text-sm font-mono font-semibold ${accent ? 'text-[hsl(var(--accent-primary-hsl))]' : 'text-foreground'}`}>{value}</span>
  </div>
);

// ============ Performance Card ============

const PerformanceCard: React.FC<{ metrics: PerformanceMetrics; title: string }> = ({ metrics, title }) => (
  <Card variant="gradient" padding="md" className="animate-fade-in">
    <div className="mb-3">
      <span className="label-uppercase">{title}</span>
    </div>
    <MetricRow label="方向准确率" value={pct(metrics.directionAccuracyPct)} accent />
    <MetricRow label="胜率" value={pct(metrics.winRatePct)} accent />
    <MetricRow label="平均模拟收益" value={pct(metrics.avgSimulatedReturnPct)} />
    <MetricRow label="平均标的收益" value={pct(metrics.avgStockReturnPct)} />
    <MetricRow label="止损触发率" value={pct(metrics.stopLossTriggerRate)} />
    <MetricRow label="止盈触发率" value={pct(metrics.takeProfitTriggerRate)} />
    <MetricRow label="平均命中天数" value={metrics.avgDaysToFirstHit != null ? metrics.avgDaysToFirstHit.toFixed(1) : '--'} />
    <div className="mt-3 pt-2 border-t border-border/40 flex items-center justify-between">
      <span className="text-xs text-muted-text">有效评估</span>
      <span className="text-xs text-secondary-text font-mono">
        {Number(metrics.completedCount)} / {Number(metrics.totalEvaluations)}
      </span>
    </div>
    <div className="flex items-center justify-between">
      <span className="text-xs text-muted-text">赢 / 亏 / 平</span>
      <span className="text-xs font-mono">
        <span className="text-success">{metrics.winCount}</span>
        {' / '}
        <span className="text-danger">{metrics.lossCount}</span>
        {' / '}
        <span className="text-[hsl(var(--accent-warning-hsl))]">{metrics.neutralCount}</span>
      </span>
    </div>
  </Card>
);

const PerformanceNoticeCard: React.FC<{ notice: PerformanceNotice }> = ({ notice }) => {
  const isDanger = notice.tone === 'danger';
  return (
    <Card
      padding="md"
      className={`
        animate-fade-in border
        ${isDanger ? 'border-danger/25 bg-danger/10' : 'border-warning/25 bg-warning/10'}
      `}
    >
      <div className="flex items-start gap-2">
        <div className={`mt-0.5 h-2.5 w-2.5 rounded-full ${isDanger ? 'bg-danger' : 'bg-[hsl(var(--accent-warning-hsl))]'}`} />
        <div className="min-w-0">
          <p className={`text-xs font-medium ${isDanger ? 'text-danger' : 'text-[hsl(var(--accent-warning-hsl))]'}`}>
            {isDanger ? '表现数据加载失败' : '表现汇总尚未生成'}
          </p>
          <p className="mt-1 text-xs leading-5 text-secondary-text">
            {notice.message}
          </p>
        </div>
      </div>
    </Card>
  );
};

const RuleMetricRow: React.FC<{ label: string; value: string; accent?: boolean }> = ({ label, value, accent }) => (
  <div className="flex items-center justify-between border-b border-white/5 py-1.5 last:border-0">
    <span className="text-xs text-secondary-text">{label}</span>
    <span className={`text-sm font-mono font-semibold ${accent ? 'text-[hsl(var(--accent-primary-hsl))]' : 'text-foreground'}`}>{value}</span>
  </div>
);

const RuleBacktestChart: React.FC<{ points: Array<{ date?: string; equity?: number; cumulativeReturnPct?: number; drawdownPct?: number }> }> = ({ points }) => {
  const geometry = useMemo(() => {
    if (!points.length) return null;
    const width = 800;
    const height = 220;
    const paddingX = 28;
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
    const mid = points[Math.floor(points.length / 2)];
    const last = points[points.length - 1];
    return {
      width,
      height,
      polyline: coords.join(' '),
      min,
      max,
      first,
      mid,
      last,
    };
  }, [points]);

  if (!geometry) {
    return (
      <div className="rounded-lg border border-dashed border-white/10 bg-elevated px-3 py-8 text-center text-xs text-muted-text">
        暂无曲线数据。
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-white/6 bg-card/72 p-3">
      <div className="mb-3 flex items-center justify-between">
        <span className="label-uppercase">权益曲线</span>
        <span className="text-xs text-muted-text font-mono">{points.length} points</span>
      </div>
      <svg viewBox={`0 0 ${geometry.width} ${geometry.height}`} className="h-[220px] w-full">
        <defs>
          <linearGradient id="rule-equity-gradient" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--accent-primary-hsl))" stopOpacity="0.9" />
            <stop offset="100%" stopColor="hsl(var(--accent-primary-hsl))" stopOpacity="0.15" />
          </linearGradient>
        </defs>
        <line x1="28" y1="20" x2="28" y2="200" stroke="rgba(255,255,255,0.08)" />
        <line x1="28" y1="200" x2="772" y2="200" stroke="rgba(255,255,255,0.08)" />
        <polyline
          fill="none"
          stroke="url(#rule-equity-gradient)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={geometry.polyline}
        />
        <polyline
          fill="rgba(82, 163, 255, 0.08)"
          stroke="none"
          points={`28,200 ${geometry.polyline} 772,200`}
        />
      </svg>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        <div className="rounded-lg border border-white/5 bg-elevated px-3 py-2">
          <p className="text-[11px] text-muted-text">起点</p>
          <p className="mt-1 text-xs font-mono text-foreground">{geometry.first?.date || '--'}</p>
          <p className="text-xs font-mono text-secondary-text">{pct(geometry.first?.cumulativeReturnPct)}</p>
        </div>
        <div className="rounded-lg border border-white/5 bg-elevated px-3 py-2">
          <p className="text-[11px] text-muted-text">中点</p>
          <p className="mt-1 text-xs font-mono text-foreground">{geometry.mid?.date || '--'}</p>
          <p className="text-xs font-mono text-secondary-text">{pct(geometry.mid?.cumulativeReturnPct)}</p>
        </div>
        <div className="rounded-lg border border-white/5 bg-elevated px-3 py-2">
          <p className="text-[11px] text-muted-text">终点</p>
          <p className="mt-1 text-xs font-mono text-foreground">{geometry.last?.date || '--'}</p>
          <p className="text-xs font-mono text-secondary-text">{pct(geometry.last?.cumulativeReturnPct)}</p>
        </div>
      </div>
    </div>
  );
};

const RuleBacktestParsedPreview: React.FC<{
  parsed: RuleBacktestParseResponse | null;
  confirmed: boolean;
  onToggleConfirmed: (value: boolean) => void;
}> = ({ parsed, confirmed, onToggleConfirmed }) => {
  if (!parsed) {
    return (
      <Card padding="md" className="border border-dashed border-white/10">
        <p className="text-xs text-muted-text">先输入策略文本并解析，系统会显示结构化规则预览。</p>
      </Card>
    );
  }

  const ambiguities = parsed.ambiguities || [];
  const needsAttention = parsed.needsConfirmation || parsed.confidence < 0.85 || ambiguities.length > 0;
  return (
    <Card padding="md" className={`border ${needsAttention ? 'border-warning/25 bg-warning/5' : 'border-success/20 bg-success/5'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <span className="label-uppercase">已解析策略</span>
          <p className="mt-1 text-xs text-secondary-text">
            解析置信度 {Math.round((parsed.confidence || 0) * 100)}% {needsAttention ? '，请先检查歧义项后再运行。' : '，可直接确认后运行。'}
          </p>
        </div>
        <Badge variant={needsAttention ? 'warning' : 'success'}>
          {needsAttention ? '需要确认' : '可运行'}
        </Badge>
      </div>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <div className="rounded-lg border border-white/6 bg-elevated px-3 py-2">
          <p className="text-[11px] text-muted-text">入场规则</p>
          <p className="mt-1 text-sm text-foreground">{parsed.summary?.entry || '--'}</p>
        </div>
        <div className="rounded-lg border border-white/6 bg-elevated px-3 py-2">
          <p className="text-[11px] text-muted-text">出场规则</p>
          <p className="mt-1 text-sm text-foreground">{parsed.summary?.exit || '--'}</p>
        </div>
      </div>
      {ambiguities.length > 0 ? (
        <div className="mt-3 rounded-lg border border-warning/20 bg-warning/10 px-3 py-2">
          <p className="text-xs font-medium text-[hsl(var(--accent-warning-hsl))]">解析提示</p>
          <ul className="mt-1 space-y-1 text-xs leading-5 text-secondary-text">
            {ambiguities.slice(0, 3).map((item, index) => (
              <li key={`${item.code || index}`} className="flex gap-2">
                <span className="text-[hsl(var(--accent-warning-hsl))]">•</span>
                <span>{String(item.message || item.suggestion || '解析需要确认')}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <label className="mt-3 flex items-center gap-2 text-xs text-secondary-text">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(e) => onToggleConfirmed(e.target.checked)}
          className="h-4 w-4 rounded border-white/20 bg-transparent"
        />
        我已确认解析结果，允许执行规则回测
      </label>
    </Card>
  );
};

const RuleBacktestTradeTable: React.FC<{ trades: RuleBacktestRunResponse['trades'] }> = ({ trades }) => {
  if (!trades.length) {
    return (
      <div className="rounded-lg border border-dashed border-white/10 bg-elevated px-3 py-8 text-center text-xs text-muted-text">
        暂无交易记录。
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-white/6 bg-card/72">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-elevated text-left">
            <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">入场</th>
            <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">出场</th>
            <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">入场原因</th>
            <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">出场原因</th>
            <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider text-right">收益率%</th>
            <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider text-right">持有天数</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade, index) => (
            <tr key={`${trade.code}-${index}`} className="border-t border-white/5 transition-colors hover:bg-hover">
              <td className="px-3 py-2 text-xs text-secondary-text">
                <div className="font-mono text-[hsl(var(--accent-primary-hsl))]">{trade.entryDate || '--'}</div>
                <div>{trade.entryPrice != null ? trade.entryPrice.toFixed(2) : '--'}</div>
              </td>
              <td className="px-3 py-2 text-xs text-secondary-text">
                <div className="font-mono text-[hsl(var(--accent-primary-hsl))]">{trade.exitDate || '--'}</div>
                <div>{trade.exitPrice != null ? trade.exitPrice.toFixed(2) : '--'}</div>
              </td>
              <td className="px-3 py-2 text-xs text-foreground truncate max-w-[240px]" title={trade.entrySignal || ''}>
                {trade.entrySignal || '--'}
              </td>
              <td className="px-3 py-2 text-xs text-foreground truncate max-w-[240px]" title={trade.exitSignal || ''}>
                {trade.exitSignal || '--'}
              </td>
              <td className="px-3 py-2 text-xs font-mono text-right">
                <span className={trade.returnPct != null && trade.returnPct > 0 ? 'text-success' : trade.returnPct != null && trade.returnPct < 0 ? 'text-danger' : 'text-secondary-text'}>
                  {pct(trade.returnPct)}
                </span>
              </td>
              <td className="px-3 py-2 text-xs font-mono text-right text-foreground">{trade.holdingDays ?? '--'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// ============ Run Summary ============

const RunSummary: React.FC<{ data: BacktestRunResponse }> = ({ data }) => (
  <div className="rounded-lg border border-white/5 bg-elevated px-3 py-2 text-xs font-mono animate-fade-in">
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <span className="text-secondary-text">已处理: <span className="text-foreground">{data.processed}</span></span>
      <span className="text-secondary-text">已写入: <span className="text-[hsl(var(--accent-primary-hsl))]">{data.saved}</span></span>
      <span className="text-secondary-text">已完成: <span className="text-success">{data.completed}</span></span>
      <span className="text-secondary-text">样本不足: <span className="text-[hsl(var(--accent-warning-hsl))]">{data.insufficient}</span></span>
      {data.errors > 0 && (
        <span className="text-secondary-text">异常: <span className="text-danger">{data.errors}</span></span>
      )}
    </div>
    {data.noResultMessage ? (
      <div className="mt-2 rounded-md border border-warning/20 bg-warning/10 px-2.5 py-2 text-xs leading-5 text-warning">
        {data.noResultMessage}
      </div>
    ) : null}
  </div>
);

// ============ Main Page ============

const BacktestPage: React.FC = () => {
  // Set page title
  useEffect(() => {
    document.title = '策略回测 - WolfyStock';
  }, []);

  // Input state
  const [codeFilter, setCodeFilter] = useState('');
  const [evalDays, setEvalDays] = useState('');
  const [sampleRange, setSampleRange] = useState('60');
  const [customSampleCount, setCustomSampleCount] = useState('252');
  const [forceRerun, setForceRerun] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState<BacktestRunResponse | null>(null);
  const [runError, setRunError] = useState<ParsedApiError | null>(null);
  const [prepareResult, setPrepareResult] = useState<PrepareBacktestSamplesResponse | null>(null);
  const [prepareError, setPrepareError] = useState<ParsedApiError | null>(null);
  const [isPreparingSamples, setIsPreparingSamples] = useState(false);
  const [pageError, setPageError] = useState<ParsedApiError | null>(null);
  const [historyError, setHistoryError] = useState<ParsedApiError | null>(null);
  const [sampleStatusError, setSampleStatusError] = useState<ParsedApiError | null>(null);
  const [ruleStrategyText, setRuleStrategyText] = useState(
    'Buy when MA5 > MA20 and RSI6 < 40.\nSell when MA5 < MA20 or RSI6 > 70.',
  );
  const [ruleParsedStrategy, setRuleParsedStrategy] = useState<RuleBacktestParseResponse | null>(null);
  const [isParsingRuleStrategy, setIsParsingRuleStrategy] = useState(false);
  const [ruleParseError, setRuleParseError] = useState<ParsedApiError | null>(null);
  const [ruleRunResult, setRuleRunResult] = useState<RuleBacktestRunResponse | null>(null);
  const [isRunningRuleBacktest, setIsRunningRuleBacktest] = useState(false);
  const [ruleRunError, setRuleRunError] = useState<ParsedApiError | null>(null);
  const [ruleHistoryItems, setRuleHistoryItems] = useState<RuleBacktestHistoryItem[]>([]);
  const [ruleHistoryTotal, setRuleHistoryTotal] = useState(0);
  const [ruleHistoryPage, setRuleHistoryPage] = useState(1);
  const [isLoadingRuleHistory, setIsLoadingRuleHistory] = useState(false);
  const [ruleHistoryError, setRuleHistoryError] = useState<ParsedApiError | null>(null);
  const [selectedRuleRunId, setSelectedRuleRunId] = useState<number | null>(null);
  const [ruleConfirmed, setRuleConfirmed] = useState(false);
  const [ruleLookbackBars, setRuleLookbackBars] = useState('252');

  // Results state
  const [results, setResults] = useState<BacktestResultItem[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const pageSize = 20;
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);

  // Performance state
  const [overallPerf, setOverallPerf] = useState<PerformanceMetrics | null>(null);
  const [stockPerf, setStockPerf] = useState<PerformanceMetrics | null>(null);
  const [isLoadingPerf, setIsLoadingPerf] = useState(false);
  const [performanceNotice, setPerformanceNotice] = useState<PerformanceNotice | null>(null);
  const [sampleStatus, setSampleStatus] = useState<BacktestSampleStatusResponse | null>(null);
  const [historyItems, setHistoryItems] = useState<BacktestRunHistoryItem[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingSampleStatus, setIsLoadingSampleStatus] = useState(false);

  // Fetch results
  const fetchResults = useCallback(async (
    page = 1,
    code?: string,
    windowDays?: number,
    runId?: number | null,
  ) => {
    setIsLoadingResults(true);
    try {
      const response = await backtestApi.getResults({
        code: code || undefined,
        evalWindowDays: windowDays,
        runId: runId || undefined,
        page,
        limit: pageSize,
      });
      setResults(response.items);
      setTotalResults(response.total);
      setCurrentPage(response.page);
      setPageError(null);
    } catch (err) {
      console.error('Failed to fetch backtest results:', err);
      setPageError(getParsedApiError(err));
    } finally {
      setIsLoadingResults(false);
    }
  }, []);

  const fetchHistory = useCallback(async (page = 1, code?: string) => {
    setIsLoadingHistory(true);
    try {
      const response = await backtestApi.getHistory({ code: code || undefined, page, limit: 10 });
      setHistoryItems(response.items);
      setHistoryPage(response.page);
      setHistoryTotal(response.total);
      setHistoryError(null);
    } catch (err) {
      setHistoryError(getParsedApiError(err));
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
    } catch (err) {
      setSampleStatus(null);
      setSampleStatusError(getParsedApiError(err));
    } finally {
      setIsLoadingSampleStatus(false);
    }
  }, []);

  const fetchRuleHistory = useCallback(async (page = 1, code?: string) => {
    setIsLoadingRuleHistory(true);
    try {
      const response = await backtestApi.getRuleBacktestRuns({ code: code || undefined, page, limit: 10 });
      setRuleHistoryItems(response.items);
      setRuleHistoryTotal(response.total);
      setRuleHistoryPage(response.page);
      setRuleHistoryError(null);
    } catch (err) {
      setRuleHistoryError(getParsedApiError(err));
    } finally {
      setIsLoadingRuleHistory(false);
    }
  }, []);

  const applyRuleRunDetail = useCallback((data: RuleBacktestRunResponse) => {
    setRuleStrategyText(data.strategyText);
    setRuleLookbackBars(String(data.lookbackBars || 252));
    setRuleRunResult(data);
    setSelectedRuleRunId(data.id);
    setRuleParsedStrategy({
      code: data.code,
      strategyText: data.strategyText,
      parsedStrategy: data.parsedStrategy,
      confidence: data.parsedConfidence ?? data.parsedStrategy.confidence ?? 0,
      needsConfirmation: data.needsConfirmation,
      ambiguities: data.warnings,
      summary: (data.summary?.['parsedStrategySummary'] as Record<string, string>) || data.parsedStrategy.summary,
      maxLookback: data.parsedStrategy.maxLookback,
    });
    setRuleConfirmed(true);
  }, []);

  // Fetch performance
  const fetchPerformance = useCallback(async (
    code?: string,
    windowDays?: number,
    options: { showNotice?: boolean } = {},
  ) => {
    const { showNotice = true } = options;
    setIsLoadingPerf(true);
    const notices: string[] = [];
    let hasDanger = false;

    try {
      const overall = await backtestApi.getOverallPerformance(windowDays);
      setOverallPerf(overall);
      if (overall == null && showNotice) {
        notices.push('暂无整体回测表现汇总。');
      }
    } catch (err) {
      console.error('Failed to fetch overall performance:', err);
      setOverallPerf(null);
      hasDanger = true;
      if (showNotice) {
        notices.push(getParsedApiError(err).message);
      }
    }

    if (code) {
      try {
        const stock = await backtestApi.getStockPerformance(code, windowDays);
        setStockPerf(stock);
        if (stock == null && showNotice) {
          notices.push(`暂无 ${code} 的单股表现汇总。`);
        }
      } catch (err) {
        console.error('Failed to fetch stock performance:', err);
        setStockPerf(null);
        hasDanger = true;
        if (showNotice) {
          notices.push(getParsedApiError(err).message);
        }
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

  // Initial load — fetch performance, current results, history, and sample status
  useEffect(() => {
    const init = async () => {
      // Get latest performance (unfiltered returns most recent summary)
      const overall = await backtestApi.getOverallPerformance();
      setOverallPerf(overall);
      // Use the summary's eval_window_days to filter results consistently
      const windowDays = overall?.evalWindowDays;
      if (windowDays && !evalDays) {
        setEvalDays(String(windowDays));
      }
      setPerformanceNotice(null);
      void fetchResults(1, undefined, windowDays);
      void fetchHistory(1, undefined);
      void fetchRuleHistory(1, undefined);
    };
    init();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Run backtest
  const handleRun = async () => {
    setIsRunning(true);
    setRunResult(null);
    setRunError(null);
    setPrepareResult(null);
    setPrepareError(null);
    try {
      const code = codeFilter.trim() || undefined;
      const evalWindowDays = evalDays ? parseInt(evalDays, 10) : undefined;
      setPerformanceNotice(null);
      const response = await backtestApi.run({
        code,
        force: forceRerun || undefined,
        minAgeDays: forceRerun ? 0 : undefined,
        evalWindowDays,
      });
      setRunResult(response);
      setSelectedRunId(response.runId ?? null);
      // Refresh results first so optional performance summary cannot hide valid rows.
      await fetchResults(1, codeFilter.trim() || undefined, evalWindowDays, response.runId ?? undefined);
      await fetchHistory(1, codeFilter.trim() || undefined);
      await fetchSampleStatus(codeFilter.trim() || undefined);
      await fetchPerformance(codeFilter.trim() || undefined, evalWindowDays, { showNotice: true });
    } catch (err) {
      setRunError(getParsedApiError(err));
    } finally {
      setIsRunning(false);
    }
  };

  // Filter by code
  const handleFilter = () => {
    const code = codeFilter.trim() || undefined;
    const windowDays = evalDays ? parseInt(evalDays, 10) : undefined;
    setSelectedRunId(null);
    setSelectedRuleRunId(null);
    setCurrentPage(1);
    setHistoryPage(1);
    setRuleHistoryPage(1);
    setPerformanceNotice(null);
    void fetchResults(1, code, windowDays);
    void fetchHistory(1, code);
    void fetchSampleStatus(code);
    void fetchPerformance(code, windowDays, { showNotice: true });
    void fetchRuleHistory(1, code);
  };

  const resolvedSampleCount = sampleRange === 'custom' ? parseInt(customSampleCount, 10) : parseInt(sampleRange, 10);

  const handlePrepareSamples = async (options: { forceRefresh?: boolean } = {}) => {
    const code = codeFilter.trim();
    if (!code) {
      setPrepareError({
        title: '缺少股票代码',
        message: '请输入股票代码后再准备回测样本。',
        rawMessage: '请输入股票代码后再准备回测样本。',
        category: 'missing_params',
      });
      return;
    }

    setIsPreparingSamples(true);
    setPrepareResult(null);
    setPrepareError(null);

    try {
      const evalWindowDays = evalDays ? parseInt(evalDays, 10) : undefined;
      const response = await backtestApi.prepareSamples({
        code,
        sampleCount: Number.isFinite(resolvedSampleCount) ? resolvedSampleCount : 60,
        evalWindowDays,
        forceRefresh: options.forceRefresh || false,
      });
      setPrepareResult(response);
      await fetchSampleStatus(code);
      await fetchHistory(1, code);
    } catch (err) {
      setPrepareError(getParsedApiError(err));
    } finally {
      setIsPreparingSamples(false);
    }
  };

  const handleRebuildSamples = async () => {
    const code = codeFilter.trim();
    if (!code) {
      setPrepareError({
        title: '缺少股票代码',
        message: '请输入股票代码后再重建回测样本。',
        rawMessage: '请输入股票代码后再重建回测样本。',
        category: 'missing_params',
      });
      return;
    }

    setIsPreparingSamples(true);
    setPrepareResult(null);
    setPrepareError(null);

    try {
      await backtestApi.clearSamples(code);
      setRunResult(null);
      setSelectedRunId(null);
      setResults([]);
      setTotalResults(0);
      setHistoryPage(1);
      await handlePrepareSamples({ forceRefresh: false });
      await fetchResults(1, code, evalDays ? parseInt(evalDays, 10) : undefined);
    } catch (err) {
      setPrepareError(getParsedApiError(err));
      setIsPreparingSamples(false);
    }
  };

  const handleClearSamples = async () => {
    const code = codeFilter.trim();
    if (!code) {
      setPrepareError({
        title: '缺少股票代码',
        message: '请输入股票代码后再清理回测样本。',
        rawMessage: '请输入股票代码后再清理回测样本。',
        category: 'missing_params',
      });
      return;
    }

    setIsPreparingSamples(true);
    setPrepareError(null);
    try {
      await backtestApi.clearSamples(code);
      setPrepareResult(null);
      setRunResult(null);
      setSelectedRunId(null);
      setResults([]);
      setTotalResults(0);
      setHistoryPage(1);
      setOverallPerf(null);
      setStockPerf(null);
      await fetchSampleStatus(code);
      await fetchHistory(1, code);
      await fetchResults(1, code, evalDays ? parseInt(evalDays, 10) : undefined);
      await fetchPerformance(code, evalDays ? parseInt(evalDays, 10) : undefined, { showNotice: true });
    } catch (err) {
      setPrepareError(getParsedApiError(err));
    } finally {
      setIsPreparingSamples(false);
    }
  };

  const handleClearResults = async () => {
    const code = codeFilter.trim();
    if (!code) {
      setRunError({
        title: '缺少股票代码',
        message: '请输入股票代码后再清理回测结果。',
        rawMessage: '请输入股票代码后再清理回测结果。',
        category: 'missing_params',
      });
      return;
    }

    setIsRunning(true);
    setRunError(null);
    try {
      await backtestApi.clearResults(code);
      setRunResult(null);
      setSelectedRunId(null);
      setResults([]);
      setTotalResults(0);
      setHistoryPage(1);
      await fetchHistory(1, code);
      await fetchResults(1, code, evalDays ? parseInt(evalDays, 10) : undefined);
      await fetchPerformance(code, evalDays ? parseInt(evalDays, 10) : undefined, { showNotice: true });
    } catch (err) {
      setRunError(getParsedApiError(err));
    } finally {
      setIsRunning(false);
    }
  };

  const handleOpenRun = async (run: BacktestRunHistoryItem) => {
    setSelectedRunId(run.id);
    if (run.code) {
      setCodeFilter(run.code);
    }
    setEvalDays(String(run.evalWindowDays));
    setForceRerun(false);
    setPerformanceNotice(null);
    await fetchHistory(1, run.code || undefined);
    await fetchSampleStatus(run.code || undefined);
    await fetchResults(1, run.code || undefined, run.evalWindowDays, run.id);
  };

  const handleParseRuleStrategy = async () => {
    const code = codeFilter.trim();
    if (!code) {
      setRuleParseError({
        title: '缺少股票代码',
        message: '请先输入股票代码，再解析规则策略。',
        rawMessage: '请先输入股票代码，再解析规则策略。',
        category: 'missing_params',
      });
      return;
    }

    if (!ruleStrategyText.trim()) {
      setRuleParseError({
        title: '缺少策略文本',
        message: '请输入策略文本后再解析。',
        rawMessage: '请输入策略文本后再解析。',
        category: 'missing_params',
      });
      return;
    }

    setIsParsingRuleStrategy(true);
    setRuleParseError(null);
    setRuleRunError(null);
    try {
      const response = await backtestApi.parseRuleStrategy({
        code,
        strategyText: ruleStrategyText,
      });
      setRuleParsedStrategy(response);
      setRuleConfirmed(false);
      setRuleRunResult(null);
      setSelectedRuleRunId(null);
      await fetchRuleHistory(1, code || undefined);
    } catch (err) {
      setRuleParseError(getParsedApiError(err));
    } finally {
      setIsParsingRuleStrategy(false);
    }
  };

  const handleRunRuleBacktest = async () => {
    const code = codeFilter.trim();
    if (!code) {
      setRuleRunError({
        title: '缺少股票代码',
        message: '请输入股票代码后再运行规则回测。',
        rawMessage: '请输入股票代码后再运行规则回测。',
        category: 'missing_params',
      });
      return;
    }
    if (!ruleParsedStrategy) {
      setRuleRunError({
        title: '需要先解析策略',
        message: '请先解析策略并确认规则结构，再运行回测。',
        rawMessage: '请先解析策略并确认规则结构，再运行回测。',
        category: 'validation_error',
      });
      return;
    }
    if (!ruleConfirmed) {
      setRuleRunError({
        title: '需要确认解析结果',
        message: '请勾选“我已确认解析结果”后再运行。',
        rawMessage: '请勾选“我已确认解析结果”后再运行。',
        category: 'validation_error',
      });
      return;
    }

    setIsRunningRuleBacktest(true);
    setRuleRunError(null);
    try {
      const response = await backtestApi.runRuleBacktest({
        code,
        strategyText: ruleStrategyText,
        parsedStrategy: ruleParsedStrategy.parsedStrategy,
        lookbackBars: parseInt(ruleLookbackBars, 10) || 252,
        confirmed: true,
      });
      applyRuleRunDetail(response);
      await fetchRuleHistory(1, code || undefined);
    } catch (err) {
      setRuleRunError(getParsedApiError(err));
    } finally {
      setIsRunningRuleBacktest(false);
    }
  };

  const handleOpenRuleRun = async (run: RuleBacktestHistoryItem) => {
    setSelectedRuleRunId(run.id);
    if (run.code) {
      setCodeFilter(run.code);
    }
    setRuleConfirmed(true);
    try {
      const detail = await backtestApi.getRuleBacktestRun(run.id);
      applyRuleRunDetail(detail);
    } catch (err) {
      setRuleRunError(getParsedApiError(err));
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleFilter();
    }
  };

  // Pagination
  const totalPages = Math.ceil(totalResults / pageSize);
  const handlePageChange = (page: number) => {
    const windowDays = evalDays ? parseInt(evalDays, 10) : undefined;
    fetchResults(page, codeFilter.trim() || undefined, windowDays);
  };

  return (
    <div className="workspace-page workspace-page--backtest">
      <WorkspacePageHeader
        className="flex-shrink-0"
        eyebrow="WolfyStock Quant Lab"
        title="策略回测"
        description="用统一窗口快速复盘建议方向、止盈止损触发率和历史执行质量。"
      >
        <div className="workspace-surface-muted px-3 py-3 sm:px-4">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-0 flex-[1_1_220px]">
              <input
                type="text"
                value={codeFilter}
                onChange={(e) => setCodeFilter(e.target.value.toUpperCase())}
                onKeyDown={handleKeyDown}
                placeholder="按股票代码筛选，留空则查看全部"
                disabled={isRunning}
                className="input-terminal w-full"
              />
            </div>
            <button
              type="button"
              onClick={handleFilter}
              disabled={isLoadingResults}
              className="btn-secondary flex items-center gap-1.5 whitespace-nowrap"
            >
              筛选
            </button>
            <div className="flex items-center gap-1 whitespace-nowrap">
              <span className="text-xs text-muted-text">观察窗口</span>
              <input
                type="number"
                min={1}
                max={120}
                value={evalDays}
                onChange={(e) => setEvalDays(e.target.value)}
                placeholder="10"
                disabled={isRunning}
                className="input-terminal w-14 py-2 text-center text-xs"
              />
            </div>
            <button
              type="button"
              onClick={() => setForceRerun(!forceRerun)}
              disabled={isRunning}
              className={`
                flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium
                transition-all duration-200 whitespace-nowrap border cursor-pointer
                ${forceRerun
                  ? 'border-[hsl(var(--accent-primary-hsl)/0.4)] bg-[hsl(var(--accent-primary-hsl)/0.1)] text-[hsl(var(--accent-primary-hsl))] shadow-[0_0_8px_hsl(var(--accent-primary-hsl)/0.2)]'
                  : 'border-white/10 bg-transparent text-muted-text hover:border-white/20 hover:text-secondary-text'
                }
                disabled:cursor-not-allowed disabled:opacity-50
              `}
            >
              <span
                className={`
                  inline-block h-1.5 w-1.5 rounded-full transition-colors duration-200
                  ${forceRerun ? 'bg-[hsl(var(--accent-primary-hsl))] shadow-[0_0_4px_hsl(var(--accent-primary-hsl)/0.6)]' : 'bg-border'}
                `}
              />
              强制重跑
            </button>
            <button
              type="button"
              onClick={handleRun}
              disabled={isRunning}
                className="btn-primary flex items-center gap-1.5 whitespace-nowrap"
              >
                {isRunning ? (
                <>
                  <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  运行中...
                </>
              ) : (
                '运行回测'
              )}
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2 whitespace-nowrap">
              <span className="text-xs text-muted-text">样本范围</span>
              <select
                value={sampleRange}
                onChange={(e) => setSampleRange(e.target.value)}
                disabled={isPreparingSamples}
                className="input-terminal min-w-[120px] py-2 text-xs"
              >
                <option value="20">20</option>
                <option value="60">60</option>
                <option value="120">120</option>
                <option value="252">252</option>
                <option value="custom">自定义</option>
              </select>
              {sampleRange === 'custom' ? (
                <input
                  type="number"
                  min={1}
                  max={365}
                  value={customSampleCount}
                  onChange={(e) => setCustomSampleCount(e.target.value)}
                  disabled={isPreparingSamples}
                  className="input-terminal w-20 py-2 text-center text-xs"
                />
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => handlePrepareSamples({ forceRefresh: false })}
              disabled={isRunning || isPreparingSamples || !codeFilter.trim()}
              className="btn-secondary whitespace-nowrap"
            >
              {isPreparingSamples ? '准备中...' : '准备样本'}
            </button>
            <button
              type="button"
              onClick={handleRebuildSamples}
              disabled={isRunning || isPreparingSamples || !codeFilter.trim()}
              className="btn-secondary whitespace-nowrap"
            >
              重建样本
            </button>
            <button
              type="button"
              onClick={handleClearSamples}
              disabled={isRunning || isPreparingSamples || !codeFilter.trim()}
              className="btn-secondary whitespace-nowrap"
            >
              清空样本
            </button>
          </div>
          {runResult ? <RunSummary data={runResult} /> : null}
          {runResult?.noResultReason && ['insufficient_historical_data', 'no_analysis_history', 'missing_market_history', 'no_eligible_candidates'].includes(runResult.noResultReason) ? (
            <Card padding="md" className="border border-warning/20 bg-warning/10">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-medium text-[hsl(var(--accent-warning-hsl))]">需要准备回测样本</p>
                  <p className="mt-1 text-xs leading-5 text-secondary-text">
                    {runResult.noResultMessage || '当前历史分析样本不足，先准备样本再重新运行回测。'}
                  </p>
                </div>
              <button
                  type="button"
                  onClick={() => void handlePrepareSamples({ forceRefresh: false })}
                  disabled={isRunning || isPreparingSamples || !codeFilter.trim()}
                  className="btn-secondary whitespace-nowrap"
                >
                  {isPreparingSamples ? '准备中...' : '准备回测样本'}
                </button>
              </div>
            </Card>
          ) : null}
          {prepareResult ? (
            <Card padding="md" className="border border-success/20 bg-success/10">
              <p className="text-xs font-medium text-success">回测样本已准备</p>
              <p className="mt-1 text-xs leading-5 text-secondary-text">
                已生成 {prepareResult.prepared} 条样本，跳过 {prepareResult.skippedExisting} 条已有样本。现在可以重新运行回测。
              </p>
            </Card>
          ) : null}
          {prepareError ? <ApiErrorAlert error={prepareError} /> : null}
          {runError ? <ApiErrorAlert error={runError} /> : null}
        </div>
      </WorkspacePageHeader>

      <Card padding="md" className="mb-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <span className="label-uppercase">AI 规则回测</span>
            <p className="mt-1 text-xs text-secondary-text">
              输入自然语言或半结构化策略，先解析为结构化规则，再执行 deterministic 回测。
            </p>
          </div>
          <div className="rounded-lg border border-white/6 bg-elevated px-3 py-2 text-xs text-secondary-text">
            当前标的：<span className="font-mono text-foreground">{codeFilter.trim() || '--'}</span>
          </div>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-3">
            <div>
              <label className="mb-1.5 block text-xs text-secondary-text">策略文本</label>
              <textarea
                value={ruleStrategyText}
                onChange={(e) => setRuleStrategyText(e.target.value)}
                rows={6}
                className="input-terminal min-h-[150px] w-full resize-y"
                placeholder="例如：Buy when MA5 > MA20 and RSI6 < 40. Sell when MA5 < MA20 or RSI6 > 70."
                disabled={isParsingRuleStrategy || isRunningRuleBacktest}
              />
            </div>
            <div className="grid gap-2 sm:grid-cols-3">
              <div>
                <label className="mb-1.5 block text-xs text-secondary-text">回测窗口（日线）</label>
                <input
                  type="number"
                  min={30}
                  max={2000}
                  value={ruleLookbackBars}
                  onChange={(e) => setRuleLookbackBars(e.target.value)}
                  className="input-terminal w-full py-2 text-xs"
                  disabled={isParsingRuleStrategy || isRunningRuleBacktest}
                />
              </div>
              <div className="flex items-end gap-2 sm:col-span-2">
                <button
                  type="button"
                  onClick={handleParseRuleStrategy}
                  disabled={isParsingRuleStrategy || isRunningRuleBacktest || !codeFilter.trim()}
                  className="btn-secondary whitespace-nowrap"
                >
                  {isParsingRuleStrategy ? '解析中...' : '解析策略'}
                </button>
                <button
                  type="button"
                  onClick={handleRunRuleBacktest}
                  disabled={isRunningRuleBacktest || isParsingRuleStrategy || !codeFilter.trim() || !ruleParsedStrategy || !ruleConfirmed}
                  className="btn-primary whitespace-nowrap"
                >
                  {isRunningRuleBacktest ? '运行中...' : '确认并运行'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setRuleParsedStrategy(null);
                    setRuleConfirmed(false);
                    setRuleRunResult(null);
                    setRuleRunError(null);
                    setRuleParseError(null);
                  }}
                  className="btn-secondary whitespace-nowrap"
                >
                  重置解析
                </button>
              </div>
            </div>
            {ruleParseError ? <ApiErrorAlert error={ruleParseError} /> : null}
            {ruleRunError ? <ApiErrorAlert error={ruleRunError} /> : null}
          </div>

          <div>
            <RuleBacktestParsedPreview
              parsed={ruleParsedStrategy}
              confirmed={ruleConfirmed}
              onToggleConfirmed={setRuleConfirmed}
            />
          </div>
        </div>
      </Card>

      <Card padding="md" className="mb-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <span className="label-uppercase">规则回测结果</span>
            <p className="mt-1 text-xs text-secondary-text">只展示规则执行的确定性结果，不由 AI 直接逐日决定交易。</p>
          </div>
          {selectedRuleRunId ? (
            <div className="rounded-lg border border-white/6 bg-elevated px-3 py-2 text-xs text-secondary-text">
              已选运行：<span className="font-mono text-foreground">#{selectedRuleRunId}</span>
            </div>
          ) : null}
        </div>

        {ruleRunResult ? (
          <div className="mt-4 space-y-4">
            {ruleRunResult.noResultMessage ? (
              <Card padding="md" className="border border-warning/20 bg-warning/10">
                <p className="text-xs font-medium text-[hsl(var(--accent-warning-hsl))]">无交易或结果受限</p>
                <p className="mt-1 text-xs leading-5 text-secondary-text">{ruleRunResult.noResultMessage}</p>
              </Card>
            ) : null}

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <Card padding="sm" className="border border-white/5 bg-elevated">
                <RuleMetricRow label="总收益" value={pct(ruleRunResult.totalReturnPct)} accent />
                <RuleMetricRow label="交易次数" value={String(ruleRunResult.tradeCount ?? 0)} />
              </Card>
              <Card padding="sm" className="border border-white/5 bg-elevated">
                <RuleMetricRow label="胜率" value={pct(ruleRunResult.winRatePct)} accent />
                <RuleMetricRow label="平均单笔收益" value={pct(ruleRunResult.avgTradeReturnPct)} />
              </Card>
              <Card padding="sm" className="border border-white/5 bg-elevated">
                <RuleMetricRow label="最大回撤" value={pct(ruleRunResult.maxDrawdownPct)} />
                <RuleMetricRow label="平均持有天数" value={ruleRunResult.avgHoldingDays != null ? ruleRunResult.avgHoldingDays.toFixed(1) : '--'} />
              </Card>
              <Card padding="sm" className="border border-white/5 bg-elevated">
                <RuleMetricRow label="最终权益" value={ruleRunResult.finalEquity != null ? ruleRunResult.finalEquity.toFixed(2) : '--'} accent />
                <RuleMetricRow label="交易数" value={String(ruleRunResult.tradeCount ?? 0)} />
              </Card>
            </div>

            <RuleBacktestChart points={ruleRunResult.equityCurve || []} />

            <Card padding="md" className="border border-white/6 bg-elevated">
              <span className="label-uppercase">AI 结果总结</span>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-secondary-text">
                {ruleRunResult.aiSummary || '暂无 AI 总结。'}
              </p>
            </Card>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <span className="label-uppercase">交易明细</span>
                <span className="text-xs text-muted-text">{ruleRunResult.trades?.length || 0} 笔</span>
              </div>
              <RuleBacktestTradeTable trades={ruleRunResult.trades || []} />
            </div>
          </div>
        ) : (
          <div className="mt-4 rounded-lg border border-dashed border-white/10 bg-elevated px-3 py-8 text-center text-xs text-muted-text">
            解析并运行策略后，这里会显示指标、权益曲线、交易表和 AI 总结。
          </div>
        )}
      </Card>

      <Card padding="md" className="mb-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <span className="label-uppercase">规则回测历史</span>
            <p className="mt-1 text-xs text-secondary-text">点击“查看”可回放某次规则回测结果。</p>
          </div>
          <button
            type="button"
            onClick={() => void fetchRuleHistory(1, codeFilter.trim() || undefined)}
            className="btn-secondary whitespace-nowrap"
            disabled={isLoadingRuleHistory}
          >
            {isLoadingRuleHistory ? '刷新中...' : '刷新历史'}
          </button>
        </div>

        {isLoadingRuleHistory ? (
          <div className="py-6 text-center text-xs text-muted-text">加载规则回测历史中...</div>
        ) : ruleHistoryError ? (
          <ApiErrorAlert error={ruleHistoryError} className="mt-3" />
        ) : ruleHistoryItems.length === 0 ? (
          <div className="py-6 text-center text-xs text-muted-text">暂无规则回测历史记录。</div>
        ) : (
          <div className="mt-3 overflow-x-auto rounded-xl border border-white/6 bg-card/72">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-elevated text-left">
                  <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">运行时间</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">代码</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">策略</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider text-right">交易</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider text-right">总收益</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider text-right">胜率</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">状态</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {ruleHistoryItems.map((item) => (
                  <tr
                    key={item.id}
                    className={`border-t border-white/5 transition-colors hover:bg-hover ${selectedRuleRunId === item.id ? 'bg-[hsl(var(--accent-primary-hsl)/0.06)]' : ''}`}
                  >
                    <td className="px-3 py-2 text-xs text-secondary-text">{item.runAt || '--'}</td>
                    <td className="px-3 py-2 font-mono text-xs text-[hsl(var(--accent-primary-hsl))]">{item.code}</td>
                    <td className="px-3 py-2 text-xs text-foreground truncate max-w-[260px]" title={item.strategyText}>
                      {item.strategyText}
                    </td>
                    <td className="px-3 py-2 text-xs text-right text-foreground">{item.tradeCount}</td>
                    <td className="px-3 py-2 text-xs text-right text-foreground">{pct(item.totalReturnPct)}</td>
                    <td className="px-3 py-2 text-xs text-right text-foreground">{pct(item.winRatePct)}</td>
                    <td className="px-3 py-2">{item.status === 'completed' ? <Badge variant="success">完成</Badge> : <Badge variant="warning">{item.status}</Badge>}</td>
                    <td className="px-3 py-2 text-right">
                      <button
                        type="button"
                        onClick={() => void handleOpenRuleRun(item)}
                        className="btn-secondary whitespace-nowrap"
                      >
                        查看
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-4 flex items-center justify-between gap-3">
          <p className="text-xs text-muted-text">共 {ruleHistoryTotal} 条规则回测记录</p>
          <Pagination
            currentPage={ruleHistoryPage}
            totalPages={Math.max(1, Math.ceil(ruleHistoryTotal / 10))}
            onPageChange={(page) => {
              setRuleHistoryPage(page);
              void fetchRuleHistory(page, codeFilter.trim() || undefined);
            }}
          />
        </div>
      </Card>

      {/* Main content */}
      <main className="workspace-split-layout">
        {/* Left sidebar - Performance */}
        <div className="workspace-split-rail grid gap-3">
          {isLoadingPerf ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-8 h-8 border-2 border-[hsl(var(--accent-primary-hsl)/0.2)] border-t-[hsl(var(--accent-primary-hsl))] rounded-full animate-spin" />
            </div>
          ) : (
            <>
              {performanceNotice ? <PerformanceNoticeCard notice={performanceNotice} /> : null}
              {overallPerf ? (
                <PerformanceCard metrics={overallPerf} title="整体表现" />
              ) : performanceNotice ? null : (
                <Card padding="md">
                  <p className="text-xs text-muted-text text-center py-4">
                    暂无回测表现数据。运行一次回测后，这里会显示整体命中率、收益率和止盈止损触发情况。
                  </p>
                </Card>
              )}
            </>
          )}

          {stockPerf && (
            <PerformanceCard metrics={stockPerf} title={`${stockPerf.code || codeFilter}`} />
          )}
        </div>

        {/* Right content - Results table */}
        <section className="workspace-split-main">
          <Card padding="md" className="mb-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <span className="label-uppercase">样本状态</span>
                <p className="mt-1 text-xs text-secondary-text">准备范围由上方“样本范围”控制。清空样本会删除当前 symbol 的 warmup 数据与相关结果。</p>
              </div>
              {isLoadingSampleStatus ? <span className="text-xs text-muted-text">加载中...</span> : null}
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
              <MetricRow label="已准备样本" value={sampleStatus ? String(sampleStatus.preparedCount) : '--'} />
              <MetricRow
                label="覆盖日期"
                value={sampleStatus?.preparedStartDate && sampleStatus?.preparedEndDate
                  ? `${sampleStatus.preparedStartDate} ~ ${sampleStatus.preparedEndDate}`
                  : '--'}
              />
              <MetricRow label="最新准备时间" value={sampleStatus?.latestPreparedAt || '--'} />
              <MetricRow label="当前目标范围" value={sampleRange === 'custom' ? `${customSampleCount}` : sampleRange} />
            </div>
            {prepareResult ? (
              <div className="mt-3 rounded-md border border-success/20 bg-success/10 px-3 py-2 text-xs leading-5 text-secondary-text">
                已准备 {prepareResult.prepared} 条样本，覆盖 {prepareResult.preparedStartDate || '--'} ~ {prepareResult.preparedEndDate || '--'}。
                {prepareResult.noResultMessage ? ` ${prepareResult.noResultMessage}` : ''}
              </div>
            ) : null}
          </Card>

          <div className="mb-2 flex items-center justify-between">
            <span className="label-uppercase">当前回测结果</span>
            <span className="text-xs text-muted-text">
              {selectedRunId ? `历史运行 #${selectedRunId}` : '最新运行 / 当前筛选'}
            </span>
          </div>

          {historyError ? <ApiErrorAlert error={historyError} className="mb-3" /> : null}
          {sampleStatusError ? <ApiErrorAlert error={sampleStatusError} className="mb-3" /> : null}
          {pageError ? (
            <ApiErrorAlert error={pageError} className="mb-3" />
          ) : null}
          {isLoadingResults ? (
            <div className="flex flex-col items-center justify-center h-64">
              <div className="w-10 h-10 border-3 border-[hsl(var(--accent-primary-hsl)/0.2)] border-t-[hsl(var(--accent-primary-hsl))] rounded-full animate-spin" />
              <p className="mt-3 text-secondary-text text-sm">加载回测结果中...</p>
            </div>
          ) : results.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <div className="w-12 h-12 mb-3 rounded-xl bg-elevated flex items-center justify-center">
                <svg className="w-6 h-6 text-muted-text" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
              <h3 className="text-base font-medium text-foreground mb-1.5">暂无回测结果</h3>
              <p className="text-xs text-muted-text max-w-xs">
                先运行一次回测，再查看历史分析在不同股票与窗口下的方向判断和收益表现。
              </p>
            </div>
          ) : (
            <div className="animate-fade-in">
              <div className="overflow-x-auto rounded-xl border border-white/6 bg-card/72">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-elevated text-left">
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">代码</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">日期</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">建议</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">方向</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">结果</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider text-right">收益率%</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider text-center">止损</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider text-center">止盈</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((row) => (
                      <tr
                        key={row.analysisHistoryId}
                        className="border-t border-white/5 transition-colors hover:bg-hover"
                      >
                        <td className="px-3 py-2 font-mono text-[hsl(var(--accent-primary-hsl))] text-xs">{row.code}</td>
                        <td className="px-3 py-2 text-xs text-secondary-text">{row.analysisDate || '--'}</td>
                        <td className="px-3 py-2 text-xs text-foreground truncate max-w-[140px]" title={row.operationAdvice || ''}>
                          {row.operationAdvice || '--'}
                        </td>
                        <td className="px-3 py-2 text-xs">
                          <span className="flex items-center gap-1">
                            {boolIcon(row.directionCorrect)}
                            <span className="text-muted-text">{row.directionExpected || ''}</span>
                          </span>
                        </td>
                        <td className="px-3 py-2">{outcomeBadge(row.outcome)}</td>
                        <td className="px-3 py-2 text-xs font-mono text-right">
                          <span className={
                            row.simulatedReturnPct != null
                              ? row.simulatedReturnPct > 0 ? 'text-success' : row.simulatedReturnPct < 0 ? 'text-danger' : 'text-secondary-text'
                              : 'text-muted-text'
                          }>
                            {pct(row.simulatedReturnPct)}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-center">{boolIcon(row.hitStopLoss)}</td>
                        <td className="px-3 py-2 text-center">{boolIcon(row.hitTakeProfit)}</td>
                        <td className="px-3 py-2">{statusBadge(row.evalStatus)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="mt-4">
                <Pagination
                  currentPage={currentPage}
                  totalPages={totalPages}
                  onPageChange={handlePageChange}
                />
              </div>

              <p className="text-xs text-muted-text text-center mt-2">
                共 {totalResults} 条结果
              </p>
            </div>
          )}

          <Card padding="md" className="mt-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <span className="label-uppercase">回测历史</span>
                <p className="mt-1 text-xs text-secondary-text">点击“查看”可回放某次运行的结果集。</p>
              </div>
              <button
                type="button"
                onClick={() => void handleClearResults()}
                disabled={!codeFilter.trim() || isRunning}
                className="btn-secondary whitespace-nowrap"
              >
                清空当前结果
              </button>
            </div>

            {isLoadingHistory ? (
              <div className="py-6 text-center text-xs text-muted-text">加载历史记录中...</div>
            ) : historyItems.length === 0 ? (
              <div className="py-6 text-center text-xs text-muted-text">暂无历史运行记录。</div>
            ) : (
              <div className="mt-3 overflow-x-auto rounded-xl border border-white/6 bg-card/72">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-elevated text-left">
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">运行时间</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">代码</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">窗口</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">样本</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider text-right">胜率</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider text-right">平均收益</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider">状态</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-secondary-text uppercase tracking-wider text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historyItems.map((item) => (
                      <tr
                        key={item.id}
                        className={`border-t border-white/5 transition-colors hover:bg-hover ${selectedRunId === item.id ? 'bg-[hsl(var(--accent-primary-hsl)/0.06)]' : ''}`}
                      >
                        <td className="px-3 py-2 text-xs text-secondary-text">{item.runAt || '--'}</td>
                        <td className="px-3 py-2 font-mono text-xs text-[hsl(var(--accent-primary-hsl))]">{item.code || '--'}</td>
                        <td className="px-3 py-2 text-xs text-secondary-text">{item.evalWindowDays} / {item.minAgeDays}</td>
                        <td className="px-3 py-2 text-xs text-foreground">{item.candidateCount}</td>
                        <td className="px-3 py-2 text-xs text-right text-foreground">{pct(item.winRatePct)}</td>
                        <td className="px-3 py-2 text-xs text-right text-foreground">{pct(item.avgSimulatedReturnPct)}</td>
                        <td className="px-3 py-2">{statusBadge(item.status)}</td>
                        <td className="px-3 py-2 text-right">
                          <button
                            type="button"
                            onClick={() => void handleOpenRun(item)}
                            className="btn-secondary whitespace-nowrap"
                          >
                            查看
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="mt-4 flex items-center justify-between gap-3">
              <p className="text-xs text-muted-text">共 {historyTotal} 条历史运行记录</p>
              <Pagination
                currentPage={historyPage}
                totalPages={Math.max(1, Math.ceil(historyTotal / 10))}
                onPageChange={(page) => {
                  setHistoryPage(page);
                  void fetchHistory(page, codeFilter.trim() || undefined);
                }}
              />
            </div>
          </Card>
        </section>
      </main>
    </div>
  );
};

export default BacktestPage;
