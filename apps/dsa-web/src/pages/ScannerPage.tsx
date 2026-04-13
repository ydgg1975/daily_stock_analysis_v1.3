import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { scannerApi } from '../api/scanner';
import {
  ApiErrorAlert,
  Badge,
  Button,
  Card,
  Drawer,
  Pagination,
  Select,
  WorkspacePageHeader,
} from '../components/common';
import { useI18n } from '../contexts/UiLanguageContext';
import type {
  ScannerCandidate,
  ScannerOperationalStatus,
  ScannerRunDetail,
  ScannerRunHistoryItem,
} from '../types/scanner';

const HISTORY_PAGE_SIZE = 6;

function formatTimestamp(value?: string | null): string {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function qualityVariant(hint?: string | null): 'success' | 'info' | 'warning' | 'history' {
  if (hint === '高优先级') return 'success';
  if (hint === '优先观察') return 'info';
  if (hint === '条件确认') return 'warning';
  return 'history';
}

function runStatusVariant(status?: string | null): 'success' | 'info' | 'warning' | 'danger' | 'history' {
  if (status === 'completed') return 'success';
  if (status === 'empty') return 'warning';
  if (status === 'failed') return 'danger';
  if (status === 'scheduled') return 'info';
  return 'history';
}

function notificationVariant(status?: string | null): 'success' | 'info' | 'warning' | 'danger' | 'history' {
  if (status === 'success') return 'success';
  if (status === 'not_configured') return 'history';
  if (status === 'skipped') return 'warning';
  if (status === 'failed') return 'danger';
  return 'info';
}

function reviewStatusVariant(status?: string | null): 'success' | 'warning' | 'history' {
  if (status === 'ready') return 'success';
  if (status === 'partial') return 'warning';
  return 'history';
}

function outcomeVariant(label?: string | null): 'success' | 'info' | 'danger' | 'history' {
  if (label === 'strong') return 'success';
  if (label === 'mixed') return 'info';
  if (label === 'weak') return 'danger';
  return 'history';
}

function thesisVariant(label?: string | null): 'success' | 'warning' | 'danger' | 'history' {
  if (label === 'validated') return 'success';
  if (label === 'mixed') return 'warning';
  if (label === 'not_validated') return 'danger';
  return 'history';
}

function formatPercent(value?: number | null, digits = 1): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value.toFixed(digits)}%`;
}

function formatSignedPercent(value?: number | null, digits = 1): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value >= 0 ? '+' : ''}${value.toFixed(digits)}%`;
}

function formatResolutionAttempt(attempt: unknown): string {
  if (!attempt || typeof attempt !== 'object') return '--';
  const item = attempt as Record<string, unknown>;
  const fetcher = typeof item.fetcher === 'string' ? item.fetcher : 'unknown';
  const status = typeof item.status === 'string' ? item.status : 'unknown';
  const reasonCode = typeof item.reasonCode === 'string' ? item.reasonCode : '';
  const rows = typeof item.rows === 'number' ? item.rows : null;

  if (rows != null && status === 'success') {
    return `${fetcher} · ${status} · ${rows} rows`;
  }
  if (reasonCode) {
    return `${fetcher} · ${status} · ${reasonCode}`;
  }
  return `${fetcher} · ${status}`;
}

function MetricPair({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/55 px-3 py-2">
      <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{label}</p>
      <p className="mt-1 text-sm text-foreground">{value}</p>
    </div>
  );
}

const ScannerPage: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useI18n();

  const [profile, setProfile] = useState('cn_preopen_v1');
  const [shortlistSize, setShortlistSize] = useState('5');
  const [universeLimit, setUniverseLimit] = useState('300');
  const [detailLimit, setDetailLimit] = useState('60');

  const [runDetail, setRunDetail] = useState<ScannerRunDetail | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [historyItems, setHistoryItems] = useState<ScannerRunHistoryItem[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [statusSummary, setStatusSummary] = useState<ScannerOperationalStatus | null>(null);

  const [selectedCandidate, setSelectedCandidate] = useState<ScannerCandidate | null>(null);
  const [pageError, setPageError] = useState<ParsedApiError | null>(null);
  const [historyError, setHistoryError] = useState<ParsedApiError | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isLoadingRun, setIsLoadingRun] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  useEffect(() => {
    document.title = t('scanner.documentTitle');
  }, [t]);

  const loadRun = useCallback(async (runId: number) => {
    setIsLoadingRun(true);
    try {
      const response = await scannerApi.getRun(runId);
      setRunDetail(response);
      setSelectedRunId(response.id);
      setPageError(null);
    } catch (error) {
      setPageError(getParsedApiError(error));
    } finally {
      setIsLoadingRun(false);
    }
  }, []);

  const fetchHistory = useCallback(async (page = 1, preferredRunId?: number | null) => {
    setIsLoadingHistory(true);
    try {
      const response = await scannerApi.getRecentWatchlists({
        market: 'cn',
        profile,
        limitDays: HISTORY_PAGE_SIZE,
      });
      setHistoryItems(response.items);
      setHistoryTotal(response.total);
      setHistoryPage(page);
      setHistoryError(null);

      const targetRunId = preferredRunId
        || (selectedRunId && response.items.some((item) => item.id === selectedRunId) ? selectedRunId : null)
        || response.items[0]?.id
        || null;

      if (targetRunId && targetRunId !== selectedRunId) {
        void loadRun(targetRunId);
      }
    } catch (error) {
      setHistoryError(getParsedApiError(error));
    } finally {
      setIsLoadingHistory(false);
    }
  }, [loadRun, profile, selectedRunId]);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await scannerApi.getStatus({
        market: 'cn',
        profile,
      });
      setStatusSummary(response);
      const todayRunId = response.todayWatchlist?.id;
      if (todayRunId && todayRunId !== selectedRunId) {
        void loadRun(todayRunId);
      }
    } catch {
      setStatusSummary(null);
    }
  }, [loadRun, profile, selectedRunId]);

  useEffect(() => {
    void fetchHistory(1);
    void fetchStatus();
  }, [fetchHistory, fetchStatus]);

  const handleRun = useCallback(async () => {
    setIsRunning(true);
    try {
      const response = await scannerApi.run({
        market: 'cn',
        profile,
        shortlistSize: Number.parseInt(shortlistSize, 10),
        universeLimit: Number.parseInt(universeLimit, 10),
        detailLimit: Number.parseInt(detailLimit, 10),
      });
      setRunDetail(response);
      setSelectedRunId(response.id);
      setPageError(null);
      await fetchHistory(1, response.id);
      await fetchStatus();
    } catch (error) {
      setPageError(getParsedApiError(error));
    } finally {
      setIsRunning(false);
    }
  }, [detailLimit, fetchHistory, fetchStatus, profile, shortlistSize, universeLimit]);

  const handleStartAnalysis = useCallback(async (candidate: ScannerCandidate) => {
    try {
      await analysisApi.analyzeAsync({
        stockCode: candidate.symbol,
        stockName: candidate.name,
        originalQuery: candidate.symbol,
        selectionSource: 'manual',
      });
      navigate('/');
    } catch (error) {
      if (error instanceof DuplicateTaskError) {
        navigate('/');
        return;
      }
      setPageError(getParsedApiError(error));
    }
  }, [navigate]);

  const totalHistoryPages = useMemo(
    () => Math.max(1, Math.ceil(historyTotal / HISTORY_PAGE_SIZE)),
    [historyTotal],
  );

  const latestDiagnostics = (runDetail?.diagnostics || {}) as Record<string, unknown>;
  const historyStats = (latestDiagnostics.historyStats || {}) as Record<string, unknown>;
  const scannerData = (latestDiagnostics.scannerData || {}) as Record<string, unknown>;
  const universeResolution = (scannerData.universeResolution || {}) as Record<string, unknown>;
  const snapshotResolution = (scannerData.snapshotResolution || {}) as Record<string, unknown>;
  const universeAttempts = Array.isArray(universeResolution.attempts)
    ? universeResolution.attempts.map(formatResolutionAttempt)
    : [];
  const snapshotAttempts = Array.isArray(snapshotResolution.attempts)
    ? snapshotResolution.attempts.map(formatResolutionAttempt)
    : [];
  const degradedModeDefined = Object.prototype.hasOwnProperty.call(scannerData, 'degradedModeUsed');
  const degradedModeUsed = Boolean(scannerData.degradedModeUsed);
  const showRuntimeDiagnostics = Boolean(runDetail) && (
    typeof universeResolution.source === 'string'
    || typeof snapshotResolution.source === 'string'
    || universeAttempts.length > 0
    || snapshotAttempts.length > 0
    || degradedModeDefined
  );
  const lastScheduledRun = statusSummary?.lastScheduledRun || null;
  const runNotificationStatus = runDetail?.notification?.status || statusSummary?.todayWatchlist?.notificationStatus || 'not_attempted';
  const todayWatchlistId = statusSummary?.todayWatchlist?.id ?? null;
  const isViewingTodayWatchlist = Boolean(runDetail && todayWatchlistId && runDetail.id === todayWatchlistId);
  const comparisonToPrevious = runDetail?.comparisonToPrevious;
  const currentReviewSummary = runDetail?.reviewSummary;
  const recentQualitySummary = statusSummary?.qualitySummary;

  const handleExportSummary = useCallback(() => {
    if (!runDetail) return;

    const comparison = runDetail.comparisonToPrevious;
    const review = runDetail.reviewSummary;
    const lines = [
      `# ${runDetail.headline || t('scanner.currentRunFallback')}`,
      '',
      `- ${t('scanner.metricWatchlistDate')}: ${runDetail.watchlistDate || '--'}`,
      `- ${t('scanner.metricNotification')}: ${t(`scanner.notificationStatus.${runNotificationStatus}`)}`,
      `- ${t('scanner.metricShortlist')}: ${runDetail.shortlistSize}`,
      '',
      `## ${t('scanner.shortlistTitle')}`,
      '',
    ];

    runDetail.shortlist.forEach((candidate) => {
      const outcome = candidate.realizedOutcome;
      lines.push(
        `### #${candidate.rank} ${candidate.symbol} ${candidate.name}`,
        `- Score: ${candidate.score.toFixed(1)}`,
        `- ${t('scanner.reasonListTitle')}: ${candidate.reasonSummary || '--'}`,
        `- ${t('scanner.riskTitle')}: ${(candidate.riskNotes || []).slice(0, 1).join(' / ') || '--'}`,
        `- ${t('scanner.watchTitle')}: ${(candidate.watchContext || []).slice(0, 1).map((item) => `${item.label} ${item.value}`).join(' / ') || '--'}`,
        `- ${t('scanner.reviewReturnLabel')}: ${formatSignedPercent(outcome.reviewWindowReturnPct)}`,
        `- ${t('scanner.maxFavorableLabel')}: ${formatSignedPercent(outcome.maxFavorableMovePct)} / ${t('scanner.maxAdverseLabel')}: ${formatSignedPercent(outcome.maxAdverseMovePct)}`,
        '',
      );
    });

    lines.push(`## ${t('scanner.compareTitle')}`, '');
    if (comparison?.available) {
      lines.push(
        `- ${t('scanner.comparePreviousLabel')}: ${comparison.previousWatchlistDate || '--'}`,
        `- ${t('scanner.changeNew')}: ${comparison.newSymbols.map((item) => item.symbol).join(', ') || '--'}`,
        `- ${t('scanner.changeRetained')}: ${comparison.retainedSymbols.map((item) => item.symbol).join(', ') || '--'}`,
        `- ${t('scanner.changeDropped')}: ${comparison.droppedSymbols.map((item) => item.symbol).join(', ') || '--'}`,
        '',
      );
    } else {
      lines.push(`${t('scanner.compareEmpty')}`, '');
    }

    lines.push(`## ${t('scanner.reviewTitle')}`, '');
    if (review?.available) {
      lines.push(
        `- ${t('scanner.reviewMetricReturn')}: ${formatSignedPercent(review.avgReviewWindowReturnPct)}`,
        `- ${t('scanner.reviewMetricHitRate')}: ${formatPercent(review.hitRatePct)}`,
        `- ${t('scanner.reviewMetricOutperform')}: ${formatPercent(review.outperformRatePct)}`,
        `- ${t('scanner.reviewBest')}: ${review.bestSymbol || '--'} ${formatSignedPercent(review.bestReturnPct)}`,
        `- ${t('scanner.reviewWeakest')}: ${review.weakestSymbol || '--'} ${formatSignedPercent(review.weakestReturnPct)}`,
        '',
      );
    } else {
      lines.push(`${t('scanner.reviewEmpty')}`, '');
    }

    const content = lines.join('\n');
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `scanner_review_${runDetail.watchlistDate || runDetail.id}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  }, [runDetail, runNotificationStatus, t]);

  return (
    <>
      <div className="space-y-6">
        <WorkspacePageHeader
          eyebrow={t('scanner.eyebrow')}
          title={t('scanner.title')}
          description={t('scanner.subtitle')}
        >
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(22rem,0.85fr)]">
            <Card
              title={t('scanner.runPanelTitle')}
              subtitle={t('scanner.runPanelEyebrow')}
              className="space-y-5"
            >
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Select
                  label={t('scanner.profileLabel')}
                  value={profile}
                  onChange={setProfile}
                  options={[
                    { value: 'cn_preopen_v1', label: 'A股盘前扫描 v1' },
                  ]}
                />
                <Select
                  label={t('scanner.shortlistLabel')}
                  value={shortlistSize}
                  onChange={setShortlistSize}
                  options={[
                    { value: '5', label: 'Top 5' },
                    { value: '8', label: 'Top 8' },
                    { value: '10', label: 'Top 10' },
                  ]}
                />
                <Select
                  label={t('scanner.universeLabel')}
                  value={universeLimit}
                  onChange={setUniverseLimit}
                  options={[
                    { value: '200', label: '200 只' },
                    { value: '300', label: '300 只' },
                    { value: '500', label: '500 只' },
                  ]}
                />
                <Select
                  label={t('scanner.detailLabel')}
                  value={detailLimit}
                  onChange={setDetailLimit}
                  options={[
                    { value: '40', label: '40 只' },
                    { value: '60', label: '60 只' },
                    { value: '80', label: '80 只' },
                  ]}
                />
              </div>

              <div className="grid gap-3 lg:grid-cols-2">
                <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/55 px-4 py-3">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.boundaryTitle')}</p>
                  <p className="mt-2 text-sm leading-6 text-secondary-text">
                    {t('scanner.boundaryBody')}
                  </p>
                </div>
                <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/55 px-4 py-3">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.universeTitle')}</p>
                  <p className="mt-2 text-sm leading-6 text-secondary-text">
                    {t('scanner.universeBody')}
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-secondary-text">
                  {t('scanner.runHint')}
                </p>
                <Button
                  type="button"
                  onClick={() => void handleRun()}
                  isLoading={isRunning}
                  loadingText={t('scanner.running')}
                >
                  {t('scanner.run')}
                </Button>
              </div>
            </Card>

            <Card
              title={t('scanner.currentRunTitle')}
              subtitle={t('scanner.currentRunEyebrow')}
              className="space-y-4"
            >
              {runDetail ? (
                <>
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="info">{runDetail.profileLabel || runDetail.profile}</Badge>
                      <Badge variant={runStatusVariant(runDetail.status)}>{t(`scanner.status.${runDetail.status}`)}</Badge>
                      {runDetail.triggerMode ? (
                        <Badge variant={runDetail.triggerMode === 'scheduled' ? 'info' : 'history'}>
                          {runDetail.triggerMode === 'scheduled' ? t('scanner.triggerScheduled') : t('scanner.triggerManual')}
                        </Badge>
                      ) : null}
                      {runDetail.watchlistDate ? (
                        <Badge variant="history">{runDetail.watchlistDate}</Badge>
                      ) : null}
                      <Badge variant="history">{formatTimestamp(runDetail.runAt)}</Badge>
                      <Badge variant={notificationVariant(runNotificationStatus)}>{`${t('scanner.notificationLabel')} ${t(`scanner.notificationStatus.${runNotificationStatus}`)}`}</Badge>
                    </div>
                    <h2 className="text-[1.05rem] text-foreground md:text-[1.15rem]">
                      {runDetail.headline || t('scanner.currentRunFallback')}
                    </h2>
                    <p className="text-sm leading-6 text-secondary-text">
                      {runDetail.sourceSummary}
                    </p>
                    {runDetail.failureReason ? (
                      <p className="text-sm leading-6 text-[var(--status-danger)]">
                        {runDetail.failureReason}
                      </p>
                    ) : null}
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <MetricPair label={t('scanner.metricUniverse')} value={`${runDetail.universeSize}`} />
                    <MetricPair label={t('scanner.metricDetail')} value={`${runDetail.evaluatedSize}`} />
                    <MetricPair label={t('scanner.metricHistory')} value={`${historyStats.localHits ?? 0} 本地 / ${historyStats.networkFetches ?? 0} 在线`} />
                    <MetricPair label={t('scanner.metricShortlist')} value={`${runDetail.shortlistSize}`} />
                    <MetricPair label={t('scanner.metricWatchlistDate')} value={runDetail.watchlistDate || '--'} />
                    <MetricPair label={t('scanner.metricNotification')} value={t(`scanner.notificationStatus.${runNotificationStatus}`)} />
                    <MetricPair label={t('scanner.metricSchedule')} value={statusSummary?.scheduleEnabled ? (statusSummary.scheduleTime || '--') : t('scanner.scheduleDisabled')} />
                    <MetricPair label={t('scanner.metricLastScheduled')} value={lastScheduledRun?.runAt ? formatTimestamp(lastScheduledRun.runAt) : '--'} />
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {!isViewingTodayWatchlist && todayWatchlistId ? (
                      <Button size="sm" variant="ghost" onClick={() => void loadRun(todayWatchlistId)}>
                        {t('scanner.openTodayWatchlist')}
                      </Button>
                    ) : null}
                    <Button size="sm" variant="outline" onClick={() => handleExportSummary()} disabled={!runDetail}>
                      {t('scanner.exportSummary')}
                    </Button>
                    {!isViewingTodayWatchlist && runDetail.watchlistDate ? (
                      <span className="text-xs leading-5 text-secondary-text">
                        {t('scanner.viewingHistoricalRun', { date: runDetail.watchlistDate })}
                      </span>
                    ) : null}
                  </div>
                </>
              ) : (
                <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-4 py-5 text-sm leading-6 text-secondary-text">
                  {t('scanner.currentRunEmpty')}
                </div>
              )}
            </Card>
          </div>
        </WorkspacePageHeader>

        {pageError ? <ApiErrorAlert error={pageError} /> : null}

        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1.25fr)_minmax(23rem,0.82fr)]">
          <section className="space-y-4">
            <div className="grid gap-4 xl:grid-cols-2">
              <Card
                title={t('scanner.compareTitle')}
                subtitle={t('scanner.compareEyebrow')}
                className="space-y-4"
              >
                {comparisonToPrevious?.available ? (
                  <>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="history">{`${t('scanner.comparePreviousLabel')} ${comparisonToPrevious.previousWatchlistDate || '--'}`}</Badge>
                      <Badge variant="success">{`${t('scanner.changeNew')} ${comparisonToPrevious.newCount}`}</Badge>
                      <Badge variant="info">{`${t('scanner.changeRetained')} ${comparisonToPrevious.retainedCount}`}</Badge>
                      <Badge variant="warning">{`${t('scanner.changeDropped')} ${comparisonToPrevious.droppedCount}`}</Badge>
                    </div>

                    <div className="grid gap-3 xl:grid-cols-3">
                      <div className="space-y-2">
                        <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.changeNew')}</p>
                        {comparisonToPrevious.newSymbols.length ? comparisonToPrevious.newSymbols.slice(0, 4).map((item) => (
                          <div key={`new-${item.symbol}`} className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                            <span className="text-foreground">{item.symbol}</span>
                            {item.name ? <span className="ml-2">{item.name}</span> : null}
                          </div>
                        )) : (
                          <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-3 py-2 text-sm leading-6 text-secondary-text">
                            {t('scanner.changeEmpty')}
                          </div>
                        )}
                      </div>

                      <div className="space-y-2">
                        <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.changeRetained')}</p>
                        {comparisonToPrevious.retainedSymbols.length ? comparisonToPrevious.retainedSymbols.slice(0, 4).map((item) => (
                          <div key={`retained-${item.symbol}`} className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                            <div className="flex items-center justify-between gap-3">
                              <span className="text-foreground">{item.symbol}</span>
                              {item.currentRank != null && item.previousRank != null ? (
                                <span className="text-xs text-secondary-text">
                                  {`#${item.previousRank} -> #${item.currentRank}`}
                                  {item.rankDelta != null ? ` (${item.rankDelta > 0 ? '+' : ''}${item.rankDelta})` : ''}
                                </span>
                              ) : null}
                            </div>
                            {item.name ? <p className="text-xs text-secondary-text">{item.name}</p> : null}
                          </div>
                        )) : (
                          <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-3 py-2 text-sm leading-6 text-secondary-text">
                            {t('scanner.changeEmpty')}
                          </div>
                        )}
                      </div>

                      <div className="space-y-2">
                        <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.changeDropped')}</p>
                        {comparisonToPrevious.droppedSymbols.length ? comparisonToPrevious.droppedSymbols.slice(0, 4).map((item) => (
                          <div key={`dropped-${item.symbol}`} className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                            <span className="text-foreground">{item.symbol}</span>
                            {item.name ? <span className="ml-2">{item.name}</span> : null}
                          </div>
                        )) : (
                          <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-3 py-2 text-sm leading-6 text-secondary-text">
                            {t('scanner.changeEmpty')}
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-4 py-5 text-sm leading-6 text-secondary-text">
                    {t('scanner.compareEmpty')}
                  </div>
                )}
              </Card>

              <Card
                title={t('scanner.reviewTitle')}
                subtitle={t('scanner.reviewEyebrow')}
                className="space-y-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={reviewStatusVariant(currentReviewSummary?.reviewStatus)}>
                    {t(`scanner.reviewStatus.${currentReviewSummary?.reviewStatus || 'pending'}`)}
                  </Badge>
                  {currentReviewSummary?.available ? (
                    <Badge variant="info">{`${t('scanner.reviewWindowLabel')} ${currentReviewSummary.reviewWindowDays}`}</Badge>
                  ) : null}
                </div>

                {currentReviewSummary?.available ? (
                  <>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <MetricPair label={t('scanner.reviewMetricReturn')} value={formatSignedPercent(currentReviewSummary.avgReviewWindowReturnPct)} />
                      <MetricPair label={t('scanner.reviewMetricHitRate')} value={formatPercent(currentReviewSummary.hitRatePct)} />
                      <MetricPair label={t('scanner.reviewMetricOutperform')} value={formatPercent(currentReviewSummary.outperformRatePct)} />
                      <MetricPair label={t('scanner.reviewMetricCoverage')} value={`${currentReviewSummary.reviewedCount}/${currentReviewSummary.candidateCount}`} />
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/55 px-3 py-3 text-sm leading-6 text-secondary-text">
                        <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.reviewBest')}</p>
                        <p className="mt-1 text-foreground">{`${currentReviewSummary.bestSymbol || '--'} ${formatSignedPercent(currentReviewSummary.bestReturnPct)}`}</p>
                      </div>
                      <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/55 px-3 py-3 text-sm leading-6 text-secondary-text">
                        <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.reviewWeakest')}</p>
                        <p className="mt-1 text-foreground">{`${currentReviewSummary.weakestSymbol || '--'} ${formatSignedPercent(currentReviewSummary.weakestReturnPct)}`}</p>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-4 py-5 text-sm leading-6 text-secondary-text">
                    {t('scanner.reviewEmpty')}
                  </div>
                )}
              </Card>
            </div>

            <Card
              title={t('scanner.shortlistTitle')}
              subtitle={t('scanner.shortlistEyebrow')}
              className="space-y-5"
            >
              {isLoadingRun ? (
                <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-4 py-5 text-sm text-secondary-text">
                  {t('scanner.loading')}
                </div>
              ) : null}

              {!isLoadingRun && runDetail?.shortlist?.length ? (
                <div className="grid gap-4 xl:grid-cols-2">
                  {runDetail.shortlist.map((candidate) => (
                    <Card
                      key={`${candidate.symbol}-${candidate.rank}`}
                      variant="bordered"
                      padding="md"
                      className="space-y-4"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="info">#{candidate.rank}</Badge>
                            <Badge variant={qualityVariant(candidate.qualityHint)}>
                              {candidate.qualityHint || t('scanner.defaultHint')}
                            </Badge>
                            {candidate.appearedInRecentRuns > 0 ? (
                              <Badge variant="history">
                                {`${t('scanner.repeatBadge')} ${candidate.appearedInRecentRuns}`}
                              </Badge>
                            ) : null}
                          </div>
                          <div>
                            <h3 className="text-lg text-foreground">
                              {candidate.symbol}
                              <span className="ml-2 text-sm text-secondary-text">{candidate.name}</span>
                            </h3>
                            <p className="mt-1 text-sm leading-6 text-secondary-text">
                              {candidate.reasonSummary}
                            </p>
                          </div>
                        </div>
                        <div className="min-w-[88px] text-right">
                          <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">Scanner Score</p>
                          <p className="mt-1 text-3xl leading-none text-foreground">{candidate.score.toFixed(1)}</p>
                        </div>
                      </div>

                      {candidate.boards.length ? (
                        <div className="flex flex-wrap gap-2">
                          {candidate.boards.slice(0, 3).map((board) => (
                            <Badge key={board} variant="history">{board}</Badge>
                          ))}
                        </div>
                      ) : null}

                      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                        {candidate.keyMetrics.slice(0, 6).map((metric) => (
                          <MetricPair key={`${candidate.symbol}-${metric.label}`} label={metric.label} value={metric.value} />
                        ))}
                      </div>

                      <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={reviewStatusVariant(candidate.realizedOutcome.reviewStatus)}>
                            {t(`scanner.reviewStatus.${candidate.realizedOutcome.reviewStatus}`)}
                          </Badge>
                          <Badge variant={outcomeVariant(candidate.realizedOutcome.outcomeLabel)}>
                            {t(`scanner.outcomeLabel.${candidate.realizedOutcome.outcomeLabel}`)}
                          </Badge>
                          <Badge variant={thesisVariant(candidate.realizedOutcome.thesisMatch)}>
                            {t(`scanner.thesisMatch.${candidate.realizedOutcome.thesisMatch}`)}
                          </Badge>
                        </div>
                        <div className="mt-2 grid gap-2 sm:grid-cols-3">
                          <MetricPair label={t('scanner.reviewReturnLabel')} value={formatSignedPercent(candidate.realizedOutcome.reviewWindowReturnPct)} />
                          <MetricPair label={t('scanner.maxFavorableLabel')} value={formatSignedPercent(candidate.realizedOutcome.maxFavorableMovePct)} />
                          <MetricPair label={t('scanner.maxAdverseLabel')} value={formatSignedPercent(candidate.realizedOutcome.maxAdverseMovePct)} />
                        </div>
                      </div>

                      <div className="grid gap-4 xl:grid-cols-2">
                        <div>
                          <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.riskTitle')}</p>
                          <div className="mt-2 space-y-2">
                            {candidate.riskNotes.slice(0, 2).map((note) => (
                              <div key={note} className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                                {note}
                              </div>
                            ))}
                          </div>
                        </div>
                        <div>
                          <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.watchTitle')}</p>
                          <div className="mt-2 space-y-2">
                            {candidate.watchContext.slice(0, 2).map((item) => (
                              <div key={`${candidate.symbol}-${item.label}`} className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                                <span className="text-foreground">{item.label}</span>
                                <span className="mx-2 text-muted-text">·</span>
                                <span>{item.value}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" onClick={() => void handleStartAnalysis(candidate)}>
                          {t('scanner.actionAnalyze')}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => navigate(`/chat?stock=${encodeURIComponent(candidate.symbol)}&name=${encodeURIComponent(candidate.name)}`)}
                        >
                          {t('scanner.actionAsk')}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => navigate('/backtest', { state: { prefillCode: candidate.symbol, prefillName: candidate.name } })}
                        >
                          {t('scanner.actionBacktest')}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setSelectedCandidate(candidate)}
                        >
                          {t('scanner.actionDetail')}
                        </Button>
                      </div>
                    </Card>
                  ))}
                </div>
              ) : null}

              {!isLoadingRun && !runDetail?.shortlist?.length ? (
                <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-4 py-6 text-sm leading-6 text-secondary-text">
                  <p className="text-base text-foreground">{t('scanner.emptyTitle')}</p>
                  <p className="mt-2">{t('scanner.emptyBody')}</p>
                </div>
              ) : null}
            </Card>
          </section>

          <section className="space-y-4">
            <Card
              title={t('scanner.qualityTitle')}
              subtitle={t('scanner.qualityEyebrow')}
              className="space-y-4"
            >
              {recentQualitySummary?.available ? (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="info">{`${t('scanner.reviewWindowLabel')} ${recentQualitySummary.reviewWindowDays}`}</Badge>
                    <Badge variant="history">{`${t('scanner.qualityRunsLabel')} ${recentQualitySummary.runCount}`}</Badge>
                    {recentQualitySummary.benchmarkCode ? (
                      <Badge variant="history">{`${t('scanner.benchmarkLabel')} ${recentQualitySummary.benchmarkCode}`}</Badge>
                    ) : null}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <MetricPair label={t('scanner.qualityMetricReturn')} value={formatSignedPercent(recentQualitySummary.avgShortlistReturnPct)} />
                    <MetricPair label={t('scanner.qualityMetricHitRate')} value={formatPercent(recentQualitySummary.hitRatePct)} />
                    <MetricPair label={t('scanner.qualityMetricOutperform')} value={formatPercent(recentQualitySummary.outperformRatePct)} />
                    <MetricPair label={t('scanner.qualityMetricCandidates')} value={`${recentQualitySummary.avgCandidatesPerRun ?? '--'}`} />
                    <MetricPair label={t('scanner.qualityMetricPositiveScore')} value={recentQualitySummary.positiveCandidateAvgScore != null ? recentQualitySummary.positiveCandidateAvgScore.toFixed(1) : '--'} />
                    <MetricPair label={t('scanner.qualityMetricNegativeScore')} value={recentQualitySummary.negativeCandidateAvgScore != null ? recentQualitySummary.negativeCandidateAvgScore.toFixed(1) : '--'} />
                  </div>
                </>
              ) : (
                <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-4 py-5 text-sm leading-6 text-secondary-text">
                  {t('scanner.qualityEmpty')}
                </div>
              )}
            </Card>

            <Card
              title={t('scanner.historyTitle')}
              subtitle={t('scanner.historyEyebrow')}
              className="space-y-4"
            >
              {historyError ? <ApiErrorAlert error={historyError} /> : null}

              {isLoadingHistory ? (
                <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-4 py-5 text-sm text-secondary-text">
                  {t('scanner.loadingHistory')}
                </div>
              ) : null}

              {!isLoadingHistory && historyItems.length ? (
                <div className="space-y-3">
                  {historyItems.map((item) => {
                    const isActive = item.id === selectedRunId;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => void loadRun(item.id)}
                        className={`w-full rounded-[var(--theme-panel-radius-md)] border px-4 py-3 text-left transition-colors ${
                          isActive
                            ? 'border-[var(--border-selected)] bg-[var(--overlay-selected)]'
                            : 'border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 hover:bg-[var(--overlay-hover)]'
                        }`}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="space-y-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant={isActive ? 'info' : 'history'}>{`#${item.id}`}</Badge>
                              {item.watchlistDate ? <Badge variant="history">{item.watchlistDate}</Badge> : null}
                              {item.triggerMode ? (
                                <Badge variant={item.triggerMode === 'scheduled' ? 'info' : 'history'}>
                                  {item.triggerMode === 'scheduled' ? t('scanner.triggerScheduled') : t('scanner.triggerManual')}
                                </Badge>
                              ) : null}
                              <Badge variant={runStatusVariant(item.status)}>{t(`scanner.status.${item.status}`)}</Badge>
                              {item.notificationStatus ? (
                                <Badge variant={notificationVariant(item.notificationStatus)}>
                                  {t(`scanner.notificationStatus.${item.notificationStatus}`)}
                                </Badge>
                              ) : null}
                              <Badge variant="history">{formatTimestamp(item.runAt)}</Badge>
                            </div>
                            <p className="text-sm leading-6 text-foreground">
                              {item.headline || t('scanner.currentRunFallback')}
                            </p>
                            <p className="text-xs leading-5 text-secondary-text">
                              {item.topSymbols.join(' / ') || t('scanner.noTopSymbols')}
                            </p>
                            {item.changeSummary?.available ? (
                              <p className="text-xs leading-5 text-secondary-text">
                                {`${t('scanner.changeNew')} ${item.changeSummary.newCount} · ${t('scanner.changeRetained')} ${item.changeSummary.retainedCount} · ${t('scanner.changeDropped')} ${item.changeSummary.droppedCount}`}
                              </p>
                            ) : null}
                            {item.reviewSummary?.available ? (
                              <p className="text-xs leading-5 text-secondary-text">
                                {`${t('scanner.reviewMetricReturn')} ${formatSignedPercent(item.reviewSummary.avgReviewWindowReturnPct)} · ${t('scanner.reviewMetricHitRate')} ${formatPercent(item.reviewSummary.hitRatePct)}`}
                              </p>
                            ) : (
                              <p className="text-xs leading-5 text-secondary-text">
                                {t('scanner.reviewHistoryPending')}
                              </p>
                            )}
                            {item.failureReason ? (
                              <p className="text-xs leading-5 text-[var(--status-danger)]">
                                {item.failureReason}
                              </p>
                            ) : null}
                          </div>
                          <div className="text-right text-xs text-secondary-text">
                            <p>{`${t('scanner.metricUniverse')} ${item.universeSize}`}</p>
                            <p>{`${t('scanner.metricDetail')} ${item.evaluatedSize}`}</p>
                            <p>{`${t('scanner.metricShortlist')} ${item.shortlistSize}`}</p>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              ) : null}

              {!isLoadingHistory && !historyItems.length ? (
                <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-4 py-5 text-sm leading-6 text-secondary-text">
                  {t('scanner.historyEmpty')}
                </div>
              ) : null}

              <Pagination
                currentPage={historyPage}
                totalPages={totalHistoryPages}
                onPageChange={(page) => void fetchHistory(page)}
              />
            </Card>

            <Card
              title={t('scanner.notesTitle')}
              subtitle={t('scanner.notesEyebrow')}
              className="space-y-4"
            >
              <div className="space-y-4">
                {statusSummary ? (
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.operationsTitle')}</p>
                    <div className="mt-2 grid gap-2">
                      <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                        {`${t('scanner.scheduleLabel')} ${statusSummary.scheduleEnabled ? (statusSummary.scheduleTime || '--') : t('scanner.scheduleDisabled')}`}
                      </div>
                      <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                        {`${t('scanner.lastScheduledLabel')} ${lastScheduledRun?.runAt ? formatTimestamp(lastScheduledRun.runAt) : '--'} · ${lastScheduledRun ? t(`scanner.status.${lastScheduledRun.status}`) : '--'}`}
                      </div>
                      <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                        {`${t('scanner.notificationLabel')} ${lastScheduledRun?.notificationStatus ? t(`scanner.notificationStatus.${lastScheduledRun.notificationStatus}`) : '--'}`}
                      </div>
                      {statusSummary.latestFailure?.failureReason ? (
                        <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-[var(--status-danger)]">
                          {`${t('scanner.latestFailureLabel')} ${statusSummary.latestFailure.failureReason}`}
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : null}

                {showRuntimeDiagnostics ? (
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.runtimeDiagnosticsTitle')}</p>
                    <div className="mt-2 space-y-2">
                      <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                        {`${t('scanner.universeSourceLabel')} ${String(universeResolution.source || '--')}`}
                      </div>
                      <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                        {`${t('scanner.snapshotSourceLabel')} ${String(snapshotResolution.source || runDetail?.diagnostics?.snapshotSource || '--')}`}
                      </div>
                      {degradedModeDefined ? (
                        <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                          {`${t('scanner.degradedModeLabel')} ${degradedModeUsed ? t('scanner.degradedYes') : t('scanner.degradedNo')}`}
                        </div>
                      ) : null}
                      {universeAttempts.length ? (
                        <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                          {`${t('scanner.universeAttemptsLabel')} ${universeAttempts.join(' / ')}`}
                        </div>
                      ) : null}
                      {snapshotAttempts.length ? (
                        <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                          {`${t('scanner.snapshotAttemptsLabel')} ${snapshotAttempts.join(' / ')}`}
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : null}

                <div>
                  <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.universeNotesTitle')}</p>
                  <div className="mt-2 space-y-2">
                    {(runDetail?.universeNotes || []).map((note) => (
                      <div key={note} className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                        {note}
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.scoringNotesTitle')}</p>
                  <div className="mt-2 space-y-2">
                    {(runDetail?.scoringNotes || []).map((note) => (
                      <div key={note} className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                        {note}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          </section>
        </div>
      </div>

      <Drawer
        isOpen={Boolean(selectedCandidate)}
        onClose={() => setSelectedCandidate(null)}
        title={selectedCandidate ? `${selectedCandidate.symbol} ${selectedCandidate.name}` : undefined}
        width="max-w-[min(92vw,38rem)]"
      >
        {selectedCandidate ? (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="info">#{selectedCandidate.rank}</Badge>
              <Badge variant={qualityVariant(selectedCandidate.qualityHint)}>
                {selectedCandidate.qualityHint || t('scanner.defaultHint')}
              </Badge>
              <Badge variant="history">{`Score ${selectedCandidate.score.toFixed(1)}`}</Badge>
            </div>

            <div className="space-y-2">
              <p className="text-sm leading-6 text-secondary-text">{selectedCandidate.reasonSummary}</p>
              <p className="text-xs leading-5 text-secondary-text">
                {`${t('scanner.lastTradeDate')} ${selectedCandidate.lastTradeDate || '--'} · ${t('scanner.scanTime')} ${formatTimestamp(selectedCandidate.scanTimestamp)}`}
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {selectedCandidate.keyMetrics.map((metric) => (
                <MetricPair key={`${selectedCandidate.symbol}-${metric.label}`} label={metric.label} value={metric.value} />
              ))}
            </div>

            <div className="space-y-3">
              <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.reviewTitle')}</p>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={reviewStatusVariant(selectedCandidate.realizedOutcome.reviewStatus)}>
                  {t(`scanner.reviewStatus.${selectedCandidate.realizedOutcome.reviewStatus}`)}
                </Badge>
                <Badge variant={outcomeVariant(selectedCandidate.realizedOutcome.outcomeLabel)}>
                  {t(`scanner.outcomeLabel.${selectedCandidate.realizedOutcome.outcomeLabel}`)}
                </Badge>
                <Badge variant={thesisVariant(selectedCandidate.realizedOutcome.thesisMatch)}>
                  {t(`scanner.thesisMatch.${selectedCandidate.realizedOutcome.thesisMatch}`)}
                </Badge>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <MetricPair label={t('scanner.sameDayLabel')} value={formatSignedPercent(selectedCandidate.realizedOutcome.sameDayCloseReturnPct)} />
                <MetricPair label={t('scanner.nextDayLabel')} value={formatSignedPercent(selectedCandidate.realizedOutcome.nextDayReturnPct)} />
                <MetricPair label={t('scanner.reviewReturnLabel')} value={formatSignedPercent(selectedCandidate.realizedOutcome.reviewWindowReturnPct)} />
                <MetricPair label={t('scanner.benchmarkLabel')} value={formatSignedPercent(selectedCandidate.realizedOutcome.benchmarkReturnPct)} />
                <MetricPair label={t('scanner.maxFavorableLabel')} value={formatSignedPercent(selectedCandidate.realizedOutcome.maxFavorableMovePct)} />
                <MetricPair label={t('scanner.maxAdverseLabel')} value={formatSignedPercent(selectedCandidate.realizedOutcome.maxAdverseMovePct)} />
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.reasonListTitle')}</p>
              {(selectedCandidate.reasons || []).map((reason) => (
                <div key={reason} className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                  {reason}
                </div>
              ))}
            </div>

            <div className="space-y-3">
              <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.featureTitle')}</p>
              {(selectedCandidate.featureSignals || []).map((signal) => (
                <div key={`${selectedCandidate.symbol}-${signal.label}`} className="flex items-center justify-between gap-3 rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm">
                  <span className="text-secondary-text">{signal.label}</span>
                  <span className="text-foreground">{signal.value}</span>
                </div>
              ))}
            </div>

            <div className="space-y-3">
              <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.riskTitle')}</p>
              {(selectedCandidate.riskNotes || []).map((note) => (
                <div key={note} className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                  {note}
                </div>
              ))}
            </div>

            <div className="space-y-3">
              <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.watchTitle')}</p>
              {(selectedCandidate.watchContext || []).map((item) => (
                <div key={`${selectedCandidate.symbol}-${item.label}`} className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                  <span className="text-foreground">{item.label}</span>
                  <span className="mx-2 text-muted-text">·</span>
                  <span>{item.value}</span>
                </div>
              ))}
            </div>

            <div className="space-y-3">
              <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.diagnosticsTitle')}</p>
              <pre className="overflow-x-auto rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-3 text-xs leading-6 text-secondary-text">
                {JSON.stringify(selectedCandidate.diagnostics || {}, null, 2)}
              </pre>
            </div>
          </div>
        ) : null}
      </Drawer>
    </>
  );
};

export default ScannerPage;
