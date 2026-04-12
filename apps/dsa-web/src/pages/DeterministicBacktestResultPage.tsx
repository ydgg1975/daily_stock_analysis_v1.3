import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { backtestApi } from '../api/backtest';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Button, Card } from '../components/common';
import {
  DeterministicAuditTable,
  DeterministicBacktestResultView,
  DeterministicTradeEventTable,
} from '../components/backtest/DeterministicBacktestResultView';
import {
  getDeterministicResultDensityCssVars,
  useDeterministicResultDensity,
} from '../components/backtest/deterministicResultDensity';
import { normalizeDeterministicBacktestResult } from '../components/backtest/normalizeDeterministicBacktestResult';
import {
  AssumptionList,
  Banner,
  Disclosure,
  RuleRunStatusBanner,
  RuleRunsTable,
  SummaryStrip,
  canCancelRuleRun,
  formatDateTime,
  formatNumber,
  getBenchmarkModeLabel,
  getRuleRunStatusDescription,
  getRuleRunStatusLabel,
  isRuleRunTerminal,
  pct,
  type RuleBenchmarkMode,
} from '../components/backtest/shared';
import ExecutionTracePanel from '../components/backtest/ExecutionTracePanel';
import {
  buildRuleStrategySummaryRows,
  formatRuleNormalizationStateLabel,
  getRuleStrategySpecSourceLabel,
  getRuleStrategyTypeLabel,
} from '../components/backtest/strategyInspectability';
import {
  downloadExecutionTraceCsv,
  downloadExecutionTraceJson,
  hasExecutionTraceRows,
} from '../components/backtest/executionTraceUtils';
import type {
  RuleBacktestCancelResponse,
  RuleBacktestHistoryItem,
  RuleBacktestRunResponse,
  RuleBacktestStatusResponse,
  StatusHistoryItem,
} from '../types/backtest';

const RULE_POLL_INTERVAL_MS = 1800;
const RESULT_HISTORY_PAGE_SIZE = 10;

type ResultPageLocationState = {
  initialRun?: RuleBacktestRunResponse;
};

type ResultPageTabKey = 'overview' | 'audit' | 'trades' | 'parameters' | 'history';

const RESULT_PAGE_TABS: Array<{ key: ResultPageTabKey; label: string }> = [
  { key: 'overview', label: '概览' },
  { key: 'audit', label: '审计明细' },
  { key: 'trades', label: '交易记录' },
  { key: 'parameters', label: '参数与假设' },
  { key: 'history', label: '历史结果' },
];

function formatStatusHistoryLabel(item: StatusHistoryItem): string {
  return `${String(item.status || '--')} · ${item.at ? formatDateTime(item.at) : '--'}`;
}

function formatSummaryLabel(key: string): string {
  return key
    .replaceAll(/([a-z])([A-Z])/g, '$1 $2')
    .replaceAll('_', ' ')
    .trim();
}

function formatWarningText(warning: Record<string, unknown>, index: number): string {
  const preferred = warning.message
    || warning.text
    || warning.detail
    || warning.reason
    || warning.code;
  if (typeof preferred === 'string' && preferred.trim()) return preferred;

  const serialized = JSON.stringify(warning);
  return serialized && serialized !== '{}' ? serialized : `warning #${index + 1}`;
}

const DeterministicBacktestResultPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { runId } = useParams<{ runId: string }>();
  const locationState = location.state as ResultPageLocationState | null;
  const initialRun = locationState?.initialRun || null;
  const parsedRunId = useMemo(() => Number.parseInt(runId || '', 10), [runId]);
  const hasValidRunId = Number.isFinite(parsedRunId) && parsedRunId > 0;

  const [run, setRun] = useState<RuleBacktestRunResponse | null>(
    initialRun && initialRun.id === parsedRunId ? initialRun : null,
  );
  const [isLoadingRun, setIsLoadingRun] = useState(!initialRun || initialRun.id !== parsedRunId);
  const [runError, setRunError] = useState<ParsedApiError | null>(null);
  const [historyItems, setHistoryItems] = useState<RuleBacktestHistoryItem[]>([]);
  const [historyError, setHistoryError] = useState<ParsedApiError | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [activeTab, setActiveTab] = useState<ResultPageTabKey>('overview');
  const [isPollingStatus, setIsPollingStatus] = useState(false);
  const [lastStatusRefreshAt, setLastStatusRefreshAt] = useState<string | null>(null);
  const [isCancellingRun, setIsCancellingRun] = useState(false);
  const [cancelError, setCancelError] = useState<ParsedApiError | null>(null);
  const density = useDeterministicResultDensity();

  const fetchRun = useCallback(async (options: { suppressLoading?: boolean } = {}) => {
    if (!hasValidRunId) return;
    const { suppressLoading = false } = options;
    if (!suppressLoading) setIsLoadingRun(true);
    try {
      const response = await backtestApi.getRuleBacktestRun(parsedRunId);
      setRun(response);
      setRunError(null);
      setCancelError(null);
      setLastStatusRefreshAt(new Date().toISOString());
    } catch (error) {
      setRunError(getParsedApiError(error));
    } finally {
      if (!suppressLoading) setIsLoadingRun(false);
    }
  }, [hasValidRunId, parsedRunId]);

  const fetchHistory = useCallback(async (code?: string) => {
    if (!code) {
      setHistoryItems([]);
      setHistoryError(null);
      return;
    }
    setIsLoadingHistory(true);
    try {
      const response = await backtestApi.getRuleBacktestRuns({
        code,
        page: 1,
        limit: RESULT_HISTORY_PAGE_SIZE,
      });
      setHistoryItems(response.items);
      setHistoryError(null);
    } catch (error) {
      setHistoryError(getParsedApiError(error));
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    if (!hasValidRunId) {
      setRun(null);
      setIsLoadingRun(false);
      return;
    }

    const seededRun = initialRun && initialRun.id === parsedRunId ? initialRun : null;
    setRun(seededRun);
    setRunError(null);
    setCancelError(null);
    setIsLoadingRun(!seededRun);
    setLastStatusRefreshAt(seededRun ? new Date().toISOString() : null);
    void fetchRun({ suppressLoading: Boolean(seededRun) });
  }, [fetchRun, hasValidRunId, initialRun, parsedRunId]);

  useEffect(() => {
    if (!run?.id || isRuleRunTerminal(run.status)) return undefined;

    let cancelled = false;
    let timer: number | undefined;

    const poll = async () => {
      if (!cancelled) setIsPollingStatus(true);
      try {
        const status = await backtestApi.getRuleBacktestRunStatus(run.id);
        if (cancelled) return;
        setRun((current) => (current ? { ...current, ...(status as RuleBacktestStatusResponse) } : current));
        setRunError(null);
        setLastStatusRefreshAt(new Date().toISOString());
        if (isRuleRunTerminal(status.status)) {
          await Promise.all([
            fetchRun({ suppressLoading: true }),
            fetchHistory(status.code),
          ]);
          return;
        }
      } catch (error) {
        if (!cancelled) setRunError(getParsedApiError(error));
      } finally {
        if (!cancelled) setIsPollingStatus(false);
      }

      if (!cancelled) timer = window.setTimeout(() => void poll(), RULE_POLL_INTERVAL_MS);
    };

    timer = window.setTimeout(() => void poll(), RULE_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [fetchHistory, fetchRun, run?.id, run?.status]);

  useEffect(() => {
    if (!run?.code) {
      setHistoryItems([]);
      return;
    }
    void fetchHistory(run.code);
  }, [fetchHistory, run?.code]);

  useEffect(() => {
    document.title = hasValidRunId
      ? `确定性回测结果 #${parsedRunId} - WolfyStock`
      : '确定性回测结果 - WolfyStock';
  }, [hasValidRunId, parsedRunId]);

  const handleOpenHistoryRun = useCallback((item: RuleBacktestHistoryItem) => {
    navigate(`/backtest/results/${item.id}`);
  }, [navigate]);

  const benchmarkSummary = run?.benchmarkSummary;
  const buyAndHoldSummary = run?.buyAndHoldSummary;
  const selectedBenchmarkLabel = benchmarkSummary
    ? String(
      benchmarkSummary.label
      || getBenchmarkModeLabel(
        (run?.benchmarkMode as RuleBenchmarkMode | undefined) || 'auto',
        run?.code,
        run?.benchmarkCode || undefined,
      ),
    )
    : '--';
  const benchmarkStatusNote = benchmarkSummary
    ? (
      benchmarkSummary.unavailableReason
      || (benchmarkSummary.resolvedMode === 'none'
        ? '未启用额外基准比较。'
        : benchmarkSummary.autoResolved
          ? `已按标的市场自动解析为 ${selectedBenchmarkLabel}。`
          : '与策略使用同一回测窗口进行比较。')
    )
    : '结果加载后显示基准说明。';
  const normalized = useMemo(
    () => (run?.status === 'completed' ? normalizeDeterministicBacktestResult(run) : null),
    [run],
  );
  const headerDescription = run
    ? `${run.code} · ${run.startDate || '--'} -> ${run.endDate || '--'} · 基准 ${selectedBenchmarkLabel}`
    : '结果页首屏只保留摘要、KPI 与统一图表工作区；审计、交易、参数和历史结果已收纳到下方标签页。';
  const parsedSummaryEntries = Object.entries(run?.parsedStrategy?.summary || {})
    .filter(([, value]) => typeof value === 'string' && value.trim())
    .map(([key, value]) => ({ label: formatSummaryLabel(key), value: String(value) }));
  const strategySummaryRows = useMemo(
    () => (run
      ? buildRuleStrategySummaryRows(run.parsedStrategy, run.code, run.startDate || '', run.endDate || '')
      : []),
    [run],
  );
  const strategyWarningEntries = Array.from(
    new Set([
      ...(run?.parsedStrategy?.parseWarnings || []).map((warning, index) => formatWarningText(warning, index)),
      ...(run?.warnings || []).map((warning, index) => formatWarningText(warning, index)),
    ].filter(Boolean)),
  );
  const canCancelCurrentRun = Boolean(run && canCancelRuleRun(run.status));
  const canExportTrace = Boolean(run && hasExecutionTraceRows(run));
  const statusSummaryItems = run ? [
    {
      label: '当前阶段',
      value: getRuleRunStatusLabel(run.status),
      note: run.statusMessage || getRuleRunStatusDescription(run.status),
    },
    {
      label: '自动刷新',
      value: isRuleRunTerminal(run.status) ? '已停止' : '每 1.8 秒',
      note: isPollingStatus ? '正在同步最新状态' : '运行中自动轮询',
    },
    {
      label: '最近刷新',
      value: lastStatusRefreshAt ? formatDateTime(lastStatusRefreshAt) : '--',
      note: isLoadingRun ? '正在拉取详情' : '也可手动刷新',
    },
    {
      label: '下一步',
      value: canCancelCurrentRun ? '可取消' : canExportTrace ? '可导出' : isRuleRunTerminal(run.status) ? '查看结果' : '等待执行',
      note: canExportTrace ? 'CSV / JSON 导出已就绪' : '导出会在轨迹生成后可用',
    },
  ] : [];

  const handleCancelRun = useCallback(async () => {
    if (!run || !canCancelRuleRun(run.status) || isCancellingRun) return;
    const confirmed = window.confirm('确定取消当前规则回测吗？当前运行会停止继续推进，已保留的数据不会被删除。');
    if (!confirmed) return;

    setIsCancellingRun(true);
    setCancelError(null);

    try {
      const response = await backtestApi.cancelRuleBacktestRun(run.id);
      setRun((current) => (current ? { ...current, ...(response as RuleBacktestCancelResponse) } : current));
      setRunError(null);
      setLastStatusRefreshAt(new Date().toISOString());
      await Promise.all([
        fetchRun({ suppressLoading: true }),
        fetchHistory(response.code),
      ]);
    } catch (error) {
      setCancelError(getParsedApiError(error));
    } finally {
      setIsCancellingRun(false);
    }
  }, [fetchHistory, fetchRun, isCancellingRun, run]);

  const renderRunStatusSection = () => {
    if (!run && isLoadingRun) {
      return (
        <section className="backtest-display-section" data-testid="deterministic-result-page-status">
          <Card title="运行状态" subtitle="结果页正在加载" className="product-section-card product-section-card--backtest-result">
            <div className="product-empty-state product-empty-state--compact">正在加载确定性回测结果…</div>
          </Card>
        </section>
      );
    }

    if (!run) {
      return (
        <section className="backtest-display-section" data-testid="deterministic-result-page-status">
          <Card title="运行状态" subtitle="无法显示结果" className="product-section-card product-section-card--backtest-result">
            {runError ? <ApiErrorAlert error={runError} /> : <div className="product-empty-state product-empty-state--compact">未找到可显示的运行结果。</div>}
          </Card>
        </section>
      );
    }

    return (
      <section className="backtest-display-section" data-testid="deterministic-result-page-status">
        <Card title="运行状态" subtitle="结果页负责轮询、取消与导出入口" className="product-section-card product-section-card--backtest-result">
          <RuleRunStatusBanner run={run} />
          <SummaryStrip items={statusSummaryItems} />
          {!isRuleRunTerminal(run.status) ? (
            <div className="mt-4">
              <Banner
                tone="info"
                title="页面正在自动跟踪状态"
                body="当前运行尚未结束。页面会自动轮询；完成、取消或失败后会停止刷新。"
              />
            </div>
          ) : null}
          {run.status === 'completed' ? (
            <div className="mt-4">
              <Banner
                tone="success"
                title="回测已完成"
                body="建议先看结果摘要，再按需打开审计明细、执行轨迹、交易记录和参数区。"
              />
            </div>
          ) : null}
          {run.status === 'cancelled' ? (
            <div className="mt-4">
              <Banner
                tone="warning"
                title="回测已取消"
                body="当前运行已经停止。可以返回配置页调整参数，或直接用相同参数重新发起。"
              />
            </div>
          ) : null}
          {run.status === 'failed' ? (
            <div className="mt-4">
              <Banner
                tone="danger"
                title="回测运行失败"
                body="可以返回配置页修正参数，或使用同一组参数重新发起回测。"
              />
            </div>
          ) : null}
          <div className="product-action-row mt-4">
            <Button variant="ghost" onClick={() => void fetchRun()} disabled={isCancellingRun}>
              {isPollingStatus || isLoadingRun ? '刷新中…' : '刷新状态'}
            </Button>
            {canCancelCurrentRun ? (
              <Button
                variant="danger-subtle"
                onClick={() => void handleCancelRun()}
                isLoading={isCancellingRun}
                loadingText="取消中…"
              >
                取消运行
              </Button>
            ) : null}
            {isRuleRunTerminal(run.status) && canExportTrace ? (
              <>
                <Button variant="secondary" onClick={() => downloadExecutionTraceCsv(run)}>
                  导出 CSV
                </Button>
                <Button variant="ghost" onClick={() => downloadExecutionTraceJson(run)}>
                  导出 JSON
                </Button>
              </>
            ) : null}
          </div>
          {run.statusHistory?.length ? (
            <Disclosure summary={`查看状态轨迹 (${run.statusHistory.length})`}>
              <div className="product-chip-list">
                {run.statusHistory.map((item, index) => (
                  <span key={`${item.status}-${item.at || index}`} className="product-chip">
                    {index + 1}. {formatStatusHistoryLabel(item)}
                  </span>
                ))}
              </div>
            </Disclosure>
          ) : null}
          {runError ? <ApiErrorAlert error={runError} className="mt-4" /> : null}
          {cancelError ? <ApiErrorAlert error={cancelError} className="mt-4" /> : null}
        </Card>
      </section>
    );
  };

  const renderCompletedTabPanel = () => {
    if (!run || !normalized) return null;

    switch (activeTab) {
      case 'overview':
        return (
          <section
            className="backtest-display-section"
            id="deterministic-result-tab-panel-overview"
            data-testid="deterministic-result-tab-panel-overview"
            role="tabpanel"
            aria-labelledby="deterministic-result-tab-overview"
          >
            <Card title="概览" subtitle="首屏专注看图，补充说明折叠收起" className="product-section-card product-section-card--backtest-secondary">
              <p className="product-section-copy">
                日级细节已改为图表 hover 浮层；完整审计表、交易记录、参数与历史结果分别进入专门标签页，避免默认页面继续向下堆叠。
              </p>
              <SummaryStrip
                items={[
                  { label: '审计行数', value: String(normalized.viewerMeta.rowCount) },
                  { label: '交易事件', value: String(normalized.tradeEvents.length) },
                  { label: '基准收益', value: pct(run.benchmarkReturnPct) },
                  { label: '买入持有', value: pct(run.buyAndHoldReturnPct) },
                ]}
              />
              <Disclosure summary="查看基准与执行假设摘要">
                <div className="backtest-result-page__tab-stack">
                  <div className="preview-grid">
                    <div className="preview-card">
                      <p className="metric-card__label">所选基准</p>
                      <p className="preview-card__text">{selectedBenchmarkLabel}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">相对基准</p>
                      <p className="preview-card__text">{pct(run.excessReturnVsBenchmarkPct)}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">买入并持有</p>
                      <p className="preview-card__text">{buyAndHoldSummary?.label || '当前标的买入并持有'} · {pct(run.buyAndHoldReturnPct)}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">状态轨迹</p>
                      <p className="preview-card__text">{run.statusHistory.length} 个节点</p>
                    </div>
                  </div>
                  <p className="product-footnote">{benchmarkStatusNote}</p>
                  <AssumptionList assumptions={run.executionAssumptions} emptyText="暂无执行假设。" />
                </div>
              </Disclosure>
            </Card>
          </section>
        );
      case 'audit':
        return (
          <section
            className="backtest-display-section"
            id="deterministic-result-tab-panel-audit"
            data-testid="deterministic-result-tab-panel-audit"
            role="tabpanel"
            aria-labelledby="deterministic-result-tab-audit"
          >
            <ExecutionTracePanel run={run} />
            <DeterministicAuditTable run={run} rows={normalized.rows} />
          </section>
        );
      case 'trades':
        return (
          <section
            className="backtest-display-section"
            id="deterministic-result-tab-panel-trades"
            data-testid="deterministic-result-tab-panel-trades"
            role="tabpanel"
            aria-labelledby="deterministic-result-tab-trades"
          >
            <DeterministicTradeEventTable events={normalized.tradeEvents} />
          </section>
        );
      case 'parameters':
        return (
          <section
            className="backtest-display-section"
            id="deterministic-result-tab-panel-parameters"
            data-testid="deterministic-result-tab-panel-parameters"
            role="tabpanel"
            aria-labelledby="deterministic-result-tab-parameters"
          >
            <Card title="参数与假设" subtitle="参数快照、benchmark 口径与策略解释均折叠管理" className="product-section-card product-section-card--backtest-secondary">
              <SummaryStrip
                items={[
                  { label: '初始资金', value: formatNumber(run.initialCapital) },
                  { label: '回看范围', value: String(run.lookbackBars) },
                  { label: '手续费 / 滑点', value: `${formatNumber(run.feeBps, 1)}bp / ${formatNumber(run.slippageBps, 1)}bp` },
                  { label: '解析置信度', value: run.parsedConfidence == null ? '--' : pct(run.parsedConfidence * 100) },
                ]}
              />
              <div className="backtest-result-page__tab-stack">
                <Disclosure summary="参数快照">
                  <div className="preview-grid">
                    <div className="preview-card">
                      <p className="metric-card__label">标的</p>
                      <p className="preview-card__text">{run.code}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">回测区间</p>
                      <p className="preview-card__text">{run.startDate || '--'} {'->'} {run.endDate || '--'}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">提交时间</p>
                      <p className="preview-card__text">{formatDateTime(run.runAt)}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">完成时间</p>
                      <p className="preview-card__text">{formatDateTime(run.completedAt)}</p>
                    </div>
                  </div>
                </Disclosure>

                <Disclosure summary="基准与比较口径">
                  <div className="preview-grid">
                    <div className="preview-card">
                      <p className="metric-card__label">所选基准</p>
                      <p className="preview-card__text">{selectedBenchmarkLabel}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">基准收益</p>
                      <p className="preview-card__text">{pct(run.benchmarkReturnPct)}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">买入并持有</p>
                      <p className="preview-card__text">{buyAndHoldSummary?.label || '当前标的买入并持有'} · {pct(run.buyAndHoldReturnPct)}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">相对基准</p>
                      <p className="preview-card__text">{pct(run.excessReturnVsBenchmarkPct)}</p>
                    </div>
                  </div>
                  <p className="product-footnote mt-4">{benchmarkStatusNote}</p>
                </Disclosure>

                <Disclosure summary="执行假设">
                  <AssumptionList assumptions={run.executionAssumptions} emptyText="暂无执行假设。" />
                </Disclosure>

                <Disclosure summary="实际执行内容">
                  <div className="backtest-result-page__tab-stack">
                    <div className="summary-block">
                      <div className="summary-block__header">
                        <div>
                          <h3 className="summary-block__title">实际执行内容</h3>
                        </div>
                      </div>
                      <p className="product-section-copy">这里展示的是本次回测实际使用的 canonical strategy_spec，和确认页中的“实际执行内容”保持同口径。</p>
                      <div className="product-chip-list mt-4">
                        <span className="product-chip">策略族 · {getRuleStrategyTypeLabel(run.parsedStrategy)}</span>
                        <span className="product-chip">规格来源 · {getRuleStrategySpecSourceLabel(run.parsedStrategy)}</span>
                        <span className="product-chip">归一化 · {formatRuleNormalizationStateLabel(run.parsedStrategy.normalizationState)}</span>
                        <span className="product-chip">需要确认 · {run.needsConfirmation ? '是' : '否'}</span>
                        <span className="product-chip">可执行 · {run.parsedStrategy.executable ? '是' : '否'}</span>
                      </div>
                    </div>
                    <div className="preview-grid">
                      {strategySummaryRows.map((row) => (
                        <div key={`${row.label}-${row.value}`} className="preview-card">
                          <p className="metric-card__label">{row.label}</p>
                          <p className="preview-card__text">{row.value}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </Disclosure>

                <Disclosure summary="原始输入与解析">
                  <div className="backtest-result-page__tab-stack">
                    <div className="summary-block">
                      <div className="summary-block__header">
                        <div>
                          <h3 className="summary-block__title">原始输入</h3>
                        </div>
                      </div>
                      <p className="product-section-copy">{run.strategyText || '--'}</p>
                      {run.aiSummary ? <p className="product-footnote mt-3">{run.aiSummary}</p> : null}
                    </div>
                    <div className="preview-grid">
                      <div className="preview-card">
                        <p className="metric-card__label">时间框架</p>
                        <p className="preview-card__text">{run.timeframe || '--'}</p>
                      </div>
                      <div className="preview-card">
                        <p className="metric-card__label">规格来源</p>
                        <p className="preview-card__text">{getRuleStrategySpecSourceLabel(run.parsedStrategy)}</p>
                      </div>
                      <div className="preview-card">
                        <p className="metric-card__label">策略族</p>
                        <p className="preview-card__text">{getRuleStrategyTypeLabel(run.parsedStrategy)}</p>
                      </div>
                      <div className="preview-card">
                        <p className="metric-card__label">归一化状态</p>
                        <p className="preview-card__text">{formatRuleNormalizationStateLabel(run.parsedStrategy.normalizationState)}</p>
                      </div>
                    </div>
                    {parsedSummaryEntries.length ? (
                      <dl className="audit-grid">
                        {parsedSummaryEntries.map((entry) => (
                          <div key={entry.label} className="audit-grid__row">
                            <dt className="audit-grid__label">{entry.label}</dt>
                            <dd className="audit-grid__value">{entry.value}</dd>
                          </div>
                        ))}
                      </dl>
                    ) : (
                      <p className="product-empty-note">暂无额外的策略解析摘要。</p>
                    )}
                  </div>
                </Disclosure>

                <Disclosure summary="技术说明与提醒">
                  <div className="backtest-result-page__tab-stack">
                    {strategyWarningEntries.length ? (
                      <div className="summary-block">
                        <div className="summary-block__header">
                          <div>
                            <h3 className="summary-block__title">默认补全与提醒</h3>
                          </div>
                        </div>
                        <ul className="backtest-result-page__list">
                          {strategyWarningEntries.map((warning) => (
                            <li key={warning}>{warning}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {run.noResultMessage ? <p className="product-footnote">{run.noResultMessage}</p> : null}
                    {run.parsedStrategy.unsupportedReason ? <p className="product-footnote">{run.parsedStrategy.unsupportedReason}</p> : null}
                  </div>
                </Disclosure>
              </div>
            </Card>
          </section>
        );
      case 'history':
        return (
          <section
            className="backtest-display-section"
            id="deterministic-result-tab-panel-history"
            data-testid="deterministic-result-tab-panel-history"
            role="tabpanel"
            aria-labelledby="deterministic-result-tab-history"
          >
            <Card title="历史结果" subtitle="同标的运行统一走当前结果页路径" className="product-section-card product-section-card--backtest-secondary">
              <div className="summary-block__header">
                <div>
                  <h3 className="summary-block__title">同标的历史回测</h3>
                  <p className="product-section-copy">点击历史项会继续停留在 `/backtest/results/:runId` 路径，只切换当前运行 ID 和对应结果数据。</p>
                </div>
                <Button variant="ghost" onClick={() => void fetchHistory(run.code)} disabled={isLoadingHistory}>
                  {isLoadingHistory ? '刷新中…' : '刷新'}
                </Button>
              </div>
              {historyError ? <ApiErrorAlert error={historyError} className="mb-4" /> : null}
              <RuleRunsTable rows={historyItems} selectedRunId={run.id} onOpen={handleOpenHistoryRun} />
            </Card>
          </section>
        );
      default:
        return null;
    }
  };

  return (
    <div
      className="theme-page-transition backtest-v1-page workspace-page--backtest backtest-result-page"
      data-testid="deterministic-backtest-result-page"
      data-density={density.mode}
      style={getDeterministicResultDensityCssVars(density)}
    >
      <section className="backtest-result-page__hero" data-testid="deterministic-result-page-hero">
        <div className="backtest-result-page__hero-copy">
          <p className="backtest-result-page__hero-eyebrow">WolfyStock</p>
          <h1 className="backtest-result-page__hero-title">
            {hasValidRunId ? `确定性回测结果 #${parsedRunId}` : '确定性回测结果'}
          </h1>
          <p className="backtest-result-page__hero-meta">{headerDescription}</p>
        </div>
        <div className="backtest-result-page__hero-actions">
          <Button variant="ghost" size={density.buttonSize} onClick={() => navigate('/backtest')}>
            返回配置页
          </Button>
          {run ? (
            <Button
              variant="secondary"
              size={density.buttonSize}
              onClick={() => navigate('/backtest', { state: { draftRun: run } })}
            >
              用相同参数重跑
            </Button>
          ) : null}
          <Button variant="ghost" size={density.buttonSize} onClick={() => void fetchRun()}>
            刷新结果
          </Button>
        </div>
      </section>

      {!hasValidRunId ? (
        <section className="backtest-display-section">
          <Card title="无效运行 ID" subtitle="结果页无法解析参数" className="product-section-card product-section-card--backtest-result">
            <div className="product-empty-state product-empty-state--compact">请从 `/backtest` 重新发起回测，或从历史记录里打开有效的运行结果。</div>
          </Card>
        </section>
      ) : null}

      {renderRunStatusSection()}

      {run?.status === 'completed' && normalized ? (
        <>
          <section className="backtest-display-section backtest-result-page__dashboard-stage" data-testid="deterministic-result-page-dashboard-stage">
            <DeterministicBacktestResultView run={run} normalized={normalized} densityConfig={density} />
          </section>

          <section className="backtest-display-section backtest-result-page__tabs-stage" data-testid="deterministic-result-page-tabs">
            <div className="backtest-mode-toggle backtest-result-page__tabs" role="tablist" aria-label="结果详情标签">
              {RESULT_PAGE_TABS.map((tab) => (
                <button
                  key={tab.key}
                  id={`deterministic-result-tab-${tab.key}`}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.key}
                  aria-controls={`deterministic-result-tab-panel-${tab.key}`}
                  className={`backtest-mode-toggle__button${activeTab === tab.key ? ' is-active' : ''}`}
                  onClick={() => setActiveTab(tab.key)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </section>

          {renderCompletedTabPanel()}
        </>
      ) : null}
    </div>
  );
};

export default DeterministicBacktestResultPage;
