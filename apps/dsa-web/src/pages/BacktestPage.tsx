import type React from 'react';
import { useState, useEffect, useCallback } from 'react';
import { backtestApi } from '../api/backtest';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Card, Badge, Pagination, WorkspacePageHeader } from '../components/common';
import type {
  BacktestResultItem,
  BacktestRunResponse,
  PerformanceMetrics,
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

// ============ Run Summary ============

const RunSummary: React.FC<{ data: BacktestRunResponse }> = ({ data }) => (
  <div className="flex items-center gap-4 rounded-lg border border-white/5 bg-elevated px-3 py-2 text-xs font-mono animate-fade-in">
    <span className="text-secondary-text">已处理: <span className="text-foreground">{data.processed}</span></span>
    <span className="text-secondary-text">已写入: <span className="text-[hsl(var(--accent-primary-hsl))]">{data.saved}</span></span>
    <span className="text-secondary-text">已完成: <span className="text-success">{data.completed}</span></span>
    <span className="text-secondary-text">样本不足: <span className="text-[hsl(var(--accent-warning-hsl))]">{data.insufficient}</span></span>
    {data.errors > 0 && (
      <span className="text-secondary-text">异常: <span className="text-danger">{data.errors}</span></span>
    )}
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
  const [forceRerun, setForceRerun] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState<BacktestRunResponse | null>(null);
  const [runError, setRunError] = useState<ParsedApiError | null>(null);
  const [pageError, setPageError] = useState<ParsedApiError | null>(null);

  // Results state
  const [results, setResults] = useState<BacktestResultItem[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const pageSize = 20;

  // Performance state
  const [overallPerf, setOverallPerf] = useState<PerformanceMetrics | null>(null);
  const [stockPerf, setStockPerf] = useState<PerformanceMetrics | null>(null);
  const [isLoadingPerf, setIsLoadingPerf] = useState(false);

  // Fetch results
  const fetchResults = useCallback(async (page = 1, code?: string, windowDays?: number) => {
    setIsLoadingResults(true);
    try {
      const response = await backtestApi.getResults({ code: code || undefined, evalWindowDays: windowDays, page, limit: pageSize });
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

  // Fetch performance
  const fetchPerformance = useCallback(async (code?: string, windowDays?: number) => {
    setIsLoadingPerf(true);
    try {
      const overall = await backtestApi.getOverallPerformance(windowDays);
      setOverallPerf(overall);

      if (code) {
        const stock = await backtestApi.getStockPerformance(code, windowDays);
        setStockPerf(stock);
      } else {
        setStockPerf(null);
      }
      setPageError(null);
    } catch (err) {
      console.error('Failed to fetch performance:', err);
      setPageError(getParsedApiError(err));
    } finally {
      setIsLoadingPerf(false);
    }
  }, []);

  // Initial load — fetch performance first, then filter results by its window
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
      fetchResults(1, undefined, windowDays);
    };
    init();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Run backtest
  const handleRun = async () => {
    setIsRunning(true);
    setRunResult(null);
    setRunError(null);
    try {
      const code = codeFilter.trim() || undefined;
      const evalWindowDays = evalDays ? parseInt(evalDays, 10) : undefined;
      const response = await backtestApi.run({
        code,
        force: forceRerun || undefined,
        minAgeDays: forceRerun ? 0 : undefined,
        evalWindowDays,
      });
      setRunResult(response);
      // Refresh data with same eval_window_days
      fetchResults(1, codeFilter.trim() || undefined, evalWindowDays);
      fetchPerformance(codeFilter.trim() || undefined, evalWindowDays);
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
    setCurrentPage(1);
    fetchResults(1, code, windowDays);
    fetchPerformance(code, windowDays);
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
          {runResult ? <RunSummary data={runResult} /> : null}
          {runError ? <ApiErrorAlert error={runError} /> : null}
        </div>
      </WorkspacePageHeader>

      {/* Main content */}
      <main className="workspace-split-layout">
        {/* Left sidebar - Performance */}
        <div className="workspace-split-rail grid gap-3">
          {isLoadingPerf ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-8 h-8 border-2 border-[hsl(var(--accent-primary-hsl)/0.2)] border-t-[hsl(var(--accent-primary-hsl))] rounded-full animate-spin" />
            </div>
          ) : overallPerf ? (
            <PerformanceCard metrics={overallPerf} title="整体表现" />
          ) : (
            <Card padding="md">
              <p className="text-xs text-muted-text text-center py-4">
                暂无回测表现数据。运行一次回测后，这里会显示整体命中率、收益率和止盈止损触发情况。
              </p>
            </Card>
          )}

          {stockPerf && (
            <PerformanceCard metrics={stockPerf} title={`${stockPerf.code || codeFilter}`} />
          )}
        </div>

        {/* Right content - Results table */}
        <section className="workspace-split-main">
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
        </section>
      </main>
    </div>
  );
};

export default BacktestPage;
