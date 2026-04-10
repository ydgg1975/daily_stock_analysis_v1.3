/**
 * SpaceX live refactor: keeps the existing dashboard task/SSE/report behavior intact
 * while rebuilding the homepage into a top-only 2/3 + 1/3 workspace split.
 * The upper desktop region now holds workflow + decision summary on the left and
 * history on the right, with every lower report module returning to full-width flow.
 */
import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiErrorAlert, Button, ConfirmDialog } from '../components/common';
import { ProgressiveReportGeneration, ReportMarkdown, ReportSummary } from '../components/report';
import { CommandBar, HistoryPanel, StatusBlocks, TaskQueue } from '../components/home';
import { useI18n } from '../contexts/UiLanguageContext';
import { useDashboardLifecycle } from '../hooks';
import { useStockPoolStore } from '../stores';
import { normalizeFrontendReportContract } from '../api/reportNormalizer';
import { systemConfigApi } from '../api/systemConfig';
import type { TaskInfo } from '../types/analysis';
import { getSentimentLabel } from '../types/analysis';
import { cn } from '../utils/cn';
import { getReportControlledValueProfile } from '../utils/reportTerminology';
import { normalizeReportLanguage } from '../utils/reportLanguage';
import { selectCompletedTasksByRecency, selectPrimaryTask, sortTasksByPriority } from '../utils/taskQueue';

type LatestReportOpenState = {
  taskId: string;
  stockCode: string;
  stockName?: string;
  status: 'opening' | 'fallback';
  attempts: number;
  reportId?: number | null;
};

type LatestReportToast = {
  stockCode: string;
  stockName?: string;
};

type DecisionSummaryMetric = {
  label: string;
  value: string;
  support?: string;
  meter?: number;
};

type DecisionSummaryBlock = {
  eyebrow: string;
  title: string;
  code: string | null;
  body: string;
  metrics: DecisionSummaryMetric[];
};

const HomePage: React.FC = () => {
  const { t, language } = useI18n();
  const navigate = useNavigate();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const resultRegionRef = useRef<HTMLElement | null>(null);
  const handledCompletedTaskIdsRef = useRef<Set<string>>(new Set());
  const openingCompletedTaskIdsRef = useRef<Set<string>>(new Set());
  const highlightTimeoutRef = useRef<number | null>(null);
  const [latestReportOpenState, setLatestReportOpenState] = useState<LatestReportOpenState | null>(null);
  const [latestReportToast, setLatestReportToast] = useState<LatestReportToast | null>(null);
  const [showRuntimeExecutionSummary, setShowRuntimeExecutionSummary] = useState(false);
  const reportLanguage = normalizeReportLanguage(language);

  const {
    query,
    inputError,
    duplicateError,
    error,
    isAnalyzing,
    historyItems,
    highlightedHistoryId,
    selectedHistoryIds,
    isDeletingHistory,
    isLoadingHistory,
    isLoadingMore,
    hasMore,
    selectedReport,
    isLoadingReport,
    activeTasks,
    markdownDrawerOpen,
    setQuery,
    clearError,
    loadInitialHistory,
    refreshHistory,
    hydrateRecentTasks,
    loadMoreHistory,
    selectHistoryItem,
    toggleHistorySelection,
    toggleSelectAllVisible,
    deleteSelectedHistory,
    submitAnalysis,
    focusLatestHistoryForStock,
    clearHighlightedHistory,
    syncTaskCreated,
    syncTaskUpdated,
    syncTaskFailed,
    openMarkdownDrawer,
    closeMarkdownDrawer,
  } = useStockPoolStore((state) => state);

  useEffect(() => {
    document.title = t('home.documentTitle');
  }, [t]);

  useEffect(() => {
    let cancelled = false;
    const loadVisibility = async () => {
      try {
        const config = await systemConfigApi.getConfig(false);
        const value = config.items.find((item) => item.key === 'SHOW_RUNTIME_EXECUTION_SUMMARY')?.value;
        const normalized = String(value || '').trim().toLowerCase();
        const enabled = normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on';
        if (!cancelled) {
          setShowRuntimeExecutionSummary(enabled);
        }
      } catch {
        if (!cancelled) {
          setShowRuntimeExecutionSummary(false);
        }
      }
    };

    void loadVisibility();

    return () => {
      cancelled = true;
    };
  }, []);

  const selectedIds = useMemo(() => new Set(selectedHistoryIds), [selectedHistoryIds]);
  const taskQueueItems = useMemo(() => sortTasksByPriority(activeTasks), [activeTasks]);
  const primaryTask = useMemo(() => selectPrimaryTask(activeTasks), [activeTasks]);
  const hasRunningTasks = useMemo(
    () => activeTasks.some((task) => task.status === 'pending' || task.status === 'processing'),
    [activeTasks],
  );
  const liveCompletedReport = useMemo(() => {
    const liveReport = primaryTask?.result?.report;
    return liveReport ? normalizeFrontendReportContract(liveReport) : null;
  }, [primaryTask]);
  const displayReport = selectedReport ?? liveCompletedReport;
  const openingFinalReport = Boolean(
    primaryTask?.status === 'completed'
    && !selectedReport
    && !liveCompletedReport,
  );
  const progressiveTask = useMemo(() => {
    if (!primaryTask) {
      return null;
    }

    if (
      primaryTask.status === 'pending'
      || primaryTask.status === 'processing'
      || primaryTask.status === 'failed'
      || openingFinalReport
    ) {
      return primaryTask;
    }

    return null;
  }, [openingFinalReport, primaryTask]);

  useDashboardLifecycle({
    loadInitialHistory,
    refreshHistory,
    hydrateRecentTasks,
    syncTaskCreated,
    syncTaskUpdated,
    syncTaskFailed,
    hasRunningTasks,
  });

  const handleRetryTask = useCallback((task: TaskInfo) => {
    const retrySelectionSource = task.selectionSource === 'autocomplete'
      || task.selectionSource === 'import'
      || task.selectionSource === 'image'
      || task.selectionSource === 'manual'
      ? task.selectionSource
      : 'manual';

    void submitAnalysis({
      stockCode: task.stockCode,
      stockName: task.stockName,
      originalQuery: task.originalQuery || task.stockCode,
      selectionSource: retrySelectionSource,
    });
  }, [submitAnalysis]);

  useEffect(() => {
    const handledTaskIds = handledCompletedTaskIdsRef.current;
    const openingTaskIds = openingCompletedTaskIdsRef.current;

    return () => {
      if (highlightTimeoutRef.current) {
        window.clearTimeout(highlightTimeoutRef.current);
      }
      handledTaskIds.clear();
      openingTaskIds.clear();
    };
  }, []);

  useEffect(() => {
    if (!latestReportToast) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      setLatestReportToast(null);
    }, 3200);

    return () => window.clearTimeout(timer);
  }, [latestReportToast]);

  const attemptOpenLatestReport = useCallback(
    async (
      task: Pick<TaskInfo, 'taskId' | 'stockCode' | 'stockName'>,
      maxAttempts = 6,
      force = false,
    ) => {
      if (!force && handledCompletedTaskIdsRef.current.has(task.taskId)) {
        return;
      }
      if (openingCompletedTaskIdsRef.current.has(task.taskId)) {
        return;
      }

      openingCompletedTaskIdsRef.current.add(task.taskId);
      setLatestReportOpenState({
        taskId: task.taskId,
        stockCode: task.stockCode,
        stockName: task.stockName,
        status: 'opening',
        attempts: 0,
      });

      try {
        for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
          setLatestReportOpenState((current) => ({
            taskId: task.taskId,
            stockCode: task.stockCode,
            stockName: task.stockName,
            status: 'opening',
            attempts: attempt,
            reportId: current?.taskId === task.taskId ? current.reportId : undefined,
          }));

          const focusedId = await focusLatestHistoryForStock(task.stockCode);
          if (focusedId) {
            handledCompletedTaskIdsRef.current.add(task.taskId);
            setLatestReportOpenState(null);
            setLatestReportToast({
              stockCode: task.stockCode,
              stockName: task.stockName,
            });

            window.requestAnimationFrame(() => {
              resultRegionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });

            if (highlightTimeoutRef.current) {
              window.clearTimeout(highlightTimeoutRef.current);
            }
            highlightTimeoutRef.current = window.setTimeout(() => {
              clearHighlightedHistory();
            }, 4200);
            return;
          }

          if (attempt < maxAttempts) {
            await new Promise((resolve) => {
              window.setTimeout(resolve, attempt === 1 ? 650 : 1100);
            });
          }
        }

        handledCompletedTaskIdsRef.current.add(task.taskId);
        setLatestReportOpenState({
          taskId: task.taskId,
          stockCode: task.stockCode,
          stockName: task.stockName,
          status: 'fallback',
          attempts: maxAttempts,
        });
      } finally {
        openingCompletedTaskIdsRef.current.delete(task.taskId);
      }
    },
    [clearHighlightedHistory, focusLatestHistoryForStock],
  );

  useEffect(() => {
    const completedTasks = selectCompletedTasksByRecency(activeTasks);

    completedTasks.forEach((task) => {
      if (
        handledCompletedTaskIdsRef.current.has(task.taskId)
        || openingCompletedTaskIdsRef.current.has(task.taskId)
      ) {
        return;
      }

      void attemptOpenLatestReport(task);
    });
  }, [activeTasks, attemptOpenLatestReport]);

  const decisionSummaryBlock = useMemo<DecisionSummaryBlock>(() => {
    if (displayReport) {
      const actionProfile = getReportControlledValueProfile(displayReport.summary.operationAdvice, reportLanguage);
      const trendProfile = getReportControlledValueProfile(displayReport.summary.trendPrediction, reportLanguage);
      const sentimentScore = Number.isFinite(displayReport.summary.sentimentScore)
        ? displayReport.summary.sentimentScore
        : undefined;
      const sentimentLabel = sentimentScore !== undefined
        ? getSentimentLabel(sentimentScore, reportLanguage)
        : undefined;

      return {
        eyebrow: t('home.decision.eyebrow'),
        title: displayReport.meta.stockName || displayReport.meta.stockCode,
        code: displayReport.meta.stockCode,
        body: displayReport.summary.analysisSummary || actionProfile.value || t('home.emptyBody'),
        metrics: [
          {
            label: t('home.decision.action'),
            value: actionProfile.value || '--',
            support: actionProfile.support,
          },
          {
            label: t('home.decision.trend'),
            value: trendProfile.value || '--',
            support: trendProfile.support,
          },
          {
            label: t('home.decision.score'),
            value: sentimentScore !== undefined ? String(sentimentScore) : '--',
            support: sentimentLabel,
            meter: sentimentScore !== undefined ? Math.max(0, Math.min(100, sentimentScore)) : undefined,
          },
        ],
      };
    }

    if (progressiveTask) {
      const localizedTaskStatus = progressiveTask.status === 'pending'
        ? t('tasks.queued')
        : progressiveTask.status === 'processing'
          ? t('tasks.processing')
          : progressiveTask.status === 'completed'
            ? t('tasks.completed')
            : progressiveTask.status === 'failed'
              ? t('tasks.failed')
              : progressiveTask.status;

      return {
        eyebrow: t('home.decision.eyebrow'),
        title: progressiveTask.stockName || progressiveTask.stockCode,
        code: progressiveTask.stockCode,
        body: progressiveTask.message || t('home.decision.liveDraftBody'),
        metrics: [
          {
            label: t('home.decision.status'),
            value: localizedTaskStatus,
          },
          {
            label: t('home.decision.progress'),
            value: `${Math.min(progressiveTask.progress || 0, 100)}%`,
          },
          {
            label: t('home.decision.task'),
            value: progressiveTask.taskId,
          },
        ],
      };
    }

    return {
      eyebrow: t('home.decision.eyebrow'),
      title: t('home.emptyTitle'),
      code: null,
      body: t('home.emptyBody'),
      metrics: [
        {
          label: t('home.decision.action'),
          value: t('home.decision.awaitingTarget'),
        },
        {
          label: t('home.decision.trend'),
          value: t('home.decision.pendingAnalysis'),
        },
        {
          label: t('home.decision.state'),
          value: t('home.decision.ready'),
        },
      ],
    };
  }, [displayReport, progressiveTask, reportLanguage, t]);

  return (
    <div data-testid="home-dashboard" className="workspace-page workspace-page--home">
      <section className="home-workspace-shell">
        <header className="home-workspace-intro workspace-header">
          <p className="home-workspace-intro__eyebrow workspace-header__eyebrow">{t('home.eyebrow')}</p>
          <h1 className="home-workspace-intro__title workspace-header__title">{t('home.title')}</h1>
          <p className="home-workspace-intro__body workspace-header__body">{t('home.subtitle')}</p>
        </header>

        <section className="home-dashboard-layout" data-testid="home-dashboard-layout">
          <div className="home-dashboard-primary">
            <section className="home-workflow-strip" data-layout="workflow" data-testid="home-workflow-strip">
              <div className="home-workflow-strip__command" data-testid="home-command-region">
                <CommandBar
                  label={t('home.commandLabel')}
                  value={query}
                  placeholder={t('home.placeholder')}
                  disabled={isAnalyzing}
                  inputError={inputError}
                  onChange={setQuery}
                  onSubmit={(stockCode, stockName, selectionSource) => {
                    void submitAnalysis({
                      stockCode,
                      stockName,
                      originalQuery: query,
                      selectionSource: selectionSource ?? 'manual',
                    });
                  }}
                  onFollowUp={() => {
                    if (!displayReport?.meta.id) {
                      return;
                    }
                    const code = displayReport.meta.stockCode;
                    const name = displayReport.meta.stockName;
                    const rid = displayReport.meta.id;
                    navigate(`/chat?stock=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}&recordId=${rid}`);
                  }}
                  onViewReport={openMarkdownDrawer}
                  canFollowUp={displayReport?.meta.id !== undefined}
                  canViewReport={displayReport?.meta.id !== undefined}
                  analyzeText={t('home.analyze')}
                  analyzingText={t('home.analyzing')}
                  followUpText={t('home.followAi')}
                  reportText={t('home.viewFullReport')}
                />
              </div>

              <div className="home-workflow-strip__status" data-testid="home-status-region">
                <StatusBlocks
                  task={primaryTask}
                  isAnalyzing={isAnalyzing}
                  selectedReport={displayReport}
                  duplicateError={duplicateError}
                  error={isAnalyzing || activeTasks.length > 0 || Boolean(duplicateError) ? error : null}
                  layout="workflow"
                />
              </div>
            </section>

            <section className="home-decision-summary" aria-label={decisionSummaryBlock.eyebrow} data-testid="home-decision-summary">
              <div className="home-decision-summary__header">
                <div>
                  <p className="home-decision-summary__eyebrow">{decisionSummaryBlock.eyebrow}</p>
                  <h2 className="home-decision-summary__title">
                    {decisionSummaryBlock.title}
                    {decisionSummaryBlock.code ? (
                      <span className="home-decision-summary__code">{decisionSummaryBlock.code}</span>
                    ) : null}
                  </h2>
                </div>
                {displayReport ? (
                  <Button
                    variant="home-action-report"
                    size="sm"
                    onClick={openMarkdownDrawer}
                    className="home-decision-summary__button"
                  >
                    {t('home.viewFullReport')}
                  </Button>
                ) : null}
              </div>

              <p className="home-decision-summary__body">{decisionSummaryBlock.body}</p>

              <div className="home-decision-summary__metrics">
                {decisionSummaryBlock.metrics.map((metric) => (
                  <div key={metric.label} className="home-decision-summary__metric">
                    <p className="home-decision-summary__metric-label">{metric.label}</p>
                    <p className="home-decision-summary__metric-value">{metric.value}</p>
                    {metric.support ? (
                      <p className="home-decision-summary__metric-support">{metric.support}</p>
                    ) : null}
                    {typeof metric.meter === 'number' ? (
                      <div className="home-decision-summary__metric-meter" aria-hidden="true">
                        <span
                          className="home-decision-summary__metric-meter-fill"
                          style={{ width: `${metric.meter}%` }}
                        />
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </section>

            <TaskQueue
              tasks={taskQueueItems}
              primaryTaskId={primaryTask?.taskId || null}
              viewedStockCode={displayReport?.meta.stockCode || null}
              onTaskSelect={(task) => {
                void focusLatestHistoryForStock(task.stockCode);
              }}
            />
          </div>

          <aside className="home-dashboard-history" data-column="history" data-testid="home-history-column">
            <HistoryPanel
              items={historyItems}
              isLoading={isLoadingHistory}
              isLoadingMore={isLoadingMore}
              hasMore={hasMore}
              selectedId={displayReport?.meta.id}
              highlightedId={highlightedHistoryId}
              selectedIds={selectedIds}
              isDeleting={isDeletingHistory}
              onItemClick={(recordId) => {
                void selectHistoryItem(recordId);
              }}
              onLoadMore={() => void loadMoreHistory()}
              onToggleItemSelection={toggleHistorySelection}
              onToggleSelectAll={toggleSelectAllVisible}
              onDeleteSelected={() => setShowDeleteConfirm(true)}
            />
          </aside>
        </section>

        <section className="home-workspace-flow" data-layout="report-flow" data-testid="home-report-flow">
          {latestReportOpenState?.status === 'fallback' ? (
            <div
              className={cn(
                'theme-inline-banner theme-inline-banner--warning home-latest-report-banner px-4 py-3 transition-colors',
              )}
              data-testid="latest-report-status"
            >
              <div className="home-latest-report-banner__content">
                <div className="min-w-0">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">
                    {t('home.latestPendingTitle')}
                  </p>
                  <p className="mt-1 text-sm font-medium text-foreground">
                    {latestReportOpenState.stockName || latestReportOpenState.stockCode}
                    <span className="ml-2 text-xs font-normal text-muted-text">{latestReportOpenState.stockCode}</span>
                  </p>
                  <p className="mt-1 text-xs leading-5 text-secondary-text">
                    {t('home.latestPendingBody')}
                  </p>
                </div>
                <Button
                  variant="home-action-report"
                  size="sm"
                  onClick={() => void attemptOpenLatestReport(latestReportOpenState, 4, true)}
                >
                  {t('home.viewLatestReport')}
                </Button>
              </div>
            </div>
          ) : null}

          {error ? (
            <ApiErrorAlert
              error={error}
              className="home-report-error"
              onDismiss={clearError}
            />
          ) : null}

          <section className="home-report-stage" ref={resultRegionRef}>
            {progressiveTask ? (
              <ProgressiveReportGeneration
                task={progressiveTask}
                openingFinalReport={openingFinalReport}
                onRetry={progressiveTask.status === 'failed' ? () => handleRetryTask(progressiveTask) : undefined}
              />
            ) : isLoadingReport ? (
              <div className="report-generation-stage">
                <div className="report-generation-stage__header">
                  <p className="report-generation-stage__eyebrow">{t('home.loadingReport')}</p>
                  <h2 className="report-generation-stage__title">{t('home.loadingTitle')}</h2>
                  <p className="report-generation-stage__body">{t('home.loadingBody')}</p>
                </div>
              </div>
            ) : displayReport ? (
              <div className={cn('home-report-stage__surface', 'w-full min-w-0')}>
                <div key={displayReport.meta.id ?? displayReport.meta.queryId}>
                  <ReportSummary
                    data={displayReport}
                    showExecutionSummary={showRuntimeExecutionSummary}
                    leadSummaryMode="compact-home"
                  />
                </div>
              </div>
            ) : (
              <div className="home-report-stage__empty">
                <p className="home-report-stage__empty-eyebrow">{t('home.emptyEyebrow')}</p>
                <h2 className="home-report-stage__empty-title">{t('home.emptyTitle')}</h2>
                <p className="home-report-stage__empty-body">{t('home.emptyBody')}</p>
              </div>
            )}
          </section>
        </section>
      </section>

      {markdownDrawerOpen && displayReport?.meta.id ? (
        <ReportMarkdown
          recordId={displayReport.meta.id}
          stockName={displayReport.meta.stockName || ''}
          stockCode={displayReport.meta.stockCode}
          reportLanguage={language}
          standardReport={displayReport.details?.standardReport}
          onClose={closeMarkdownDrawer}
        />
      ) : null}

      <ConfirmDialog
        isOpen={showDeleteConfirm}
        title={t('home.deleteTitle')}
        message={
          selectedHistoryIds.length === 1
            ? t('home.deleteSingle')
            : t('home.deleteMultiple', { count: selectedHistoryIds.length })
        }
        confirmText={isDeletingHistory ? t('home.deleting') : t('home.deleteConfirm')}
        cancelText={t('home.cancel')}
        isDanger={true}
        onConfirm={() => {
          void deleteSelectedHistory();
          setShowDeleteConfirm(false);
        }}
        onCancel={() => setShowDeleteConfirm(false)}
      />

      {latestReportToast ? (
        <div
          className="pointer-events-none fixed bottom-4 right-4 z-[65] w-[min(92vw,25rem)]"
          role="status"
          aria-live="polite"
          data-testid="latest-report-toast"
        >
          <div className="theme-inline-banner theme-inline-banner--success px-4 py-3">
            <p className="theme-inline-banner-title text-[11px] uppercase tracking-[0.16em]">{t('home.toastTitle')}</p>
            <p className="mt-1 text-sm font-medium text-foreground">
              {latestReportToast.stockName || latestReportToast.stockCode}
              <span className="ml-2 text-xs font-normal text-muted-text">{latestReportToast.stockCode}</span>
            </p>
            <p className="mt-1 text-xs leading-5 text-secondary-text">
              {t('home.toastBody')}
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default HomePage;
