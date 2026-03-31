import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiErrorAlert, ConfirmDialog, Button } from '../components/common';
import { StockAutocomplete } from '../components/StockAutocomplete';
import { HistoryList } from '../components/history';
import { ReportMarkdown, ReportSummary } from '../components/report';
import { TaskPanel } from '../components/tasks';
import { useShellRail } from '../components/layout/ShellRailContext';
import { useI18n } from '../contexts/UiLanguageContext';
import { useDashboardLifecycle } from '../hooks';
import { useStockPoolStore } from '../stores';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import type { AnalysisReport, TaskInfo } from '../types/analysis';
import { cn } from '../utils/cn';
import {
  ANALYSIS_STAGE_ORDER,
  getAnalysisStageDescriptor,
  getStatusRelationCopy,
  inferAnalysisStage,
} from '../utils/analysisStatus';
import { normalizeReportLanguage } from '../utils/reportLanguage';

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

function selectPrimaryTask(tasks: TaskInfo[]): TaskInfo | null {
  if (tasks.length === 0) {
    return null;
  }

  const weight = (task: TaskInfo): number => {
    if (task.status === 'processing') {
      return 3;
    }
    if (task.status === 'pending') {
      return 2;
    }
    if (task.status === 'failed') {
      return 1;
    }
    return 0;
  };

  return [...tasks].sort((left, right) => {
    const weightDiff = weight(right) - weight(left);
    if (weightDiff !== 0) {
      return weightDiff;
    }
    return Date.parse(right.createdAt || '') - Date.parse(left.createdAt || '');
  })[0];
}

const AnalysisStatusStrip: React.FC<{
  task: TaskInfo | null;
  isAnalyzing: boolean;
  selectedReport: AnalysisReport | null;
  duplicateError: string | null;
  error: ParsedApiError | null;
}> = ({
  task,
  isAnalyzing,
  selectedReport,
  duplicateError,
  error,
}) => {
  const { t } = useI18n();
  const descriptor = getAnalysisStageDescriptor(task, {
    isSubmitting: isAnalyzing,
    selectedReport,
    globalError: error,
    duplicateError,
  });

  if (!descriptor) {
    return null;
  }

  const stage = inferAnalysisStage(task, { isSubmitting: isAnalyzing }) || descriptor.key;
  const orderedStage = stage === 'failed' ? 'generating' : stage;
  const taskError = descriptor.key === 'failed'
    ? getParsedApiError(task?.error || error || duplicateError || t('status.failed'))
    : null;
  const relationCopy = getStatusRelationCopy(task, selectedReport);

  return (
    <div
      className="workspace-status-strip mt-4 animate-in fade-in slide-in-from-top-1 duration-200"
      data-testid="analysis-status-strip"
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`workspace-status-badge ${
                descriptor.key === 'failed'
                  ? 'workspace-status-badge--failed'
                  : descriptor.key === 'completed'
                    ? 'workspace-status-badge--completed'
                    : 'workspace-status-badge--active'
              }`}
            >
              {descriptor.label}
            </span>
            {task ? (
              <span className="text-sm font-medium text-foreground">
                {task.stockName || task.stockCode}
                <span className="ml-2 text-xs font-normal text-muted-text">{task.stockCode}</span>
              </span>
            ) : null}
            {selectedReport ? (
              <span className="theme-inline-chip rounded-full px-3 py-1 text-[11px] text-muted-text">
                {t('home.currentViewing', { code: selectedReport.meta.stockCode })}
              </span>
            ) : null}
          </div>

          <p className="mt-3 text-sm font-medium text-foreground">{descriptor.summary}</p>
          {descriptor.detail ? (
            <p className="mt-1.5 text-xs leading-5 text-secondary-text">{descriptor.detail}</p>
          ) : null}
          {relationCopy ? (
            <p className="mt-2 text-xs leading-5 text-muted-text">{relationCopy}</p>
          ) : null}
          {taskError && descriptor.key === 'failed' ? (
            <p className="workspace-status-error mt-2 text-xs leading-5">
              {taskError.message}
            </p>
          ) : null}
        </div>

        <div className="grid gap-2 sm:grid-cols-6 xl:min-w-[34rem]">
          {ANALYSIS_STAGE_ORDER.map((item) => {
            const isComplete = descriptor.key !== 'failed'
              && ANALYSIS_STAGE_ORDER.indexOf(item) < ANALYSIS_STAGE_ORDER.indexOf(orderedStage);
            const isActive = descriptor.key !== 'failed' && item === orderedStage;
            return (
              <div
                key={item}
                className="workspace-status-step"
                data-active={isActive}
                data-complete={isComplete}
                data-failed={descriptor.key === 'failed' && item === orderedStage}
              >
                <span
                  className={`workspace-status-dot ${
                    descriptor.key === 'failed' && item === orderedStage
                      ? 'workspace-status-dot--failed'
                      : isComplete
                        ? 'workspace-status-dot--complete'
                        : isActive
                          ? 'workspace-status-dot--active'
                          : ''
                  }`}
                />
                <span className="truncate text-[11px] uppercase tracking-[0.14em]">
                  {t(`status.${item}`)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

const HomePage: React.FC = () => {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const { setRailContent, closeMobileRail, isConnected: hasShellRail } = useShellRail();
  const resultRegionRef = useRef<HTMLDivElement | null>(null);
  const handledCompletedTaskIdsRef = useRef<Set<string>>(new Set());
  const openingCompletedTaskIdsRef = useRef<Set<string>>(new Set());
  const highlightTimeoutRef = useRef<number | null>(null);
  const [latestReportOpenState, setLatestReportOpenState] = useState<LatestReportOpenState | null>(null);
  const [latestReportToast, setLatestReportToast] = useState<LatestReportToast | null>(null);

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
  const reportLanguage = normalizeReportLanguage(selectedReport?.meta.reportLanguage);

  useDashboardLifecycle({
    loadInitialHistory,
    refreshHistory,
    hydrateRecentTasks,
    syncTaskCreated,
    syncTaskUpdated,
    syncTaskFailed,
  });

  const selectedIds = useMemo(() => new Set(selectedHistoryIds), [selectedHistoryIds]);
  const primaryTask = useMemo(() => selectPrimaryTask(activeTasks), [activeTasks]);

  const sidebarContent = useMemo(
    () => (
      <div className="flex h-full min-h-0 flex-col overflow-hidden">
        <HistoryList
          items={historyItems}
          isLoading={isLoadingHistory}
          isLoadingMore={isLoadingMore}
          hasMore={hasMore}
          selectedId={selectedReport?.meta.id}
          highlightedId={highlightedHistoryId}
          selectedIds={selectedIds}
          isDeleting={isDeletingHistory}
          onItemClick={(recordId) => {
            void selectHistoryItem(recordId);
            if (hasShellRail) {
              closeMobileRail();
            } else {
              setSidebarOpen(false);
            }
          }}
          onLoadMore={() => void loadMoreHistory()}
          onToggleItemSelection={toggleHistorySelection}
          onToggleSelectAll={toggleSelectAllVisible}
          onDeleteSelected={() => setShowDeleteConfirm(true)}
          className="min-h-0 h-full overflow-hidden"
          embedded
        />
      </div>
    ),
    [
      hasMore,
      historyItems,
      highlightedHistoryId,
      isDeletingHistory,
      isLoadingHistory,
      isLoadingMore,
      loadMoreHistory,
      selectedIds,
      selectedReport?.meta.id,
      selectHistoryItem,
      closeMobileRail,
      hasShellRail,
      toggleHistorySelection,
      toggleSelectAllVisible,
    ],
  );

  useEffect(() => {
    if (!hasShellRail) {
      return undefined;
    }
    setRailContent(sidebarContent);
    return () => setRailContent(null);
  }, [hasShellRail, setRailContent, sidebarContent]);

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
    const completedTasks = activeTasks
      .filter((task) => task.status === 'completed')
      .sort((left, right) => Date.parse(right.completedAt || right.createdAt || '') - Date.parse(left.completedAt || left.createdAt || ''));

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

  return (
    <div data-testid="home-dashboard" className="workspace-page workspace-page--home">
      <header className="workspace-header-panel overflow-hidden">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">{t('home.eyebrow')}</p>
            <h1 className="mt-2 text-xl font-semibold tracking-tight text-foreground md:text-2xl">{t('home.title')}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-secondary-text">
              {t('home.subtitle')}
            </p>
          </div>
          {!hasShellRail ? (
            <button
              onClick={() => setSidebarOpen(true)}
              className="theme-panel-subtle -mr-1 flex-shrink-0 rounded-xl p-2 text-secondary-text transition-colors hover:text-foreground xl:hidden"
              title={t('home.historyTitle')}
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          ) : null}
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-end">
          <div className="space-y-2">
            <div className="grid min-w-0 gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
              <div className="min-w-0">
                <StockAutocomplete
                  value={query}
                  onChange={setQuery}
                  onSubmit={(stockCode, stockName, selectionSource) => {
                    void submitAnalysis({
                      stockCode,
                      stockName,
                      originalQuery: query,
                      selectionSource: selectionSource ?? 'manual',
                    });
                  }}
                  placeholder={t('home.placeholder')}
                  disabled={isAnalyzing}
                  className={inputError ? 'border-danger/50' : undefined}
                />
              </div>
              <button
                type="button"
                onClick={() => void submitAnalysis()}
                disabled={!query || isAnalyzing}
                className="btn-primary flex min-w-[7rem] flex-shrink-0 items-center justify-center gap-1.5 whitespace-nowrap"
              >
                {isAnalyzing ? (
                  <>
                    <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                    {t('home.analyzing')}
                  </>
                ) : (
                  t('home.analyze')
                )}
              </button>
            </div>
            {inputError ? (
              <p className="text-xs text-danger">{inputError}</p>
            ) : null}
          </div>

          {selectedReport ? (
            <div className="flex flex-wrap items-center gap-2 xl:justify-end">
              <Button
                variant="home-action-ai"
                size="sm"
                disabled={selectedReport.meta.id === undefined}
                onClick={() => {
                  const code = selectedReport.meta.stockCode;
                  const name = selectedReport.meta.stockName;
                  const rid = selectedReport.meta.id!;
                  navigate(`/chat?stock=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}&recordId=${rid}`);
                }}
                >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                {t('home.followAi')}
              </Button>
              <Button
                variant="home-action-report"
                size="sm"
                disabled={selectedReport.meta.id === undefined}
                onClick={openMarkdownDrawer}
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                {t('home.viewFullReport')}
              </Button>
            </div>
          ) : null}
        </div>

        <AnalysisStatusStrip
          task={primaryTask}
          isAnalyzing={isAnalyzing}
          selectedReport={selectedReport}
          duplicateError={duplicateError}
          error={isAnalyzing || activeTasks.length > 0 || Boolean(duplicateError) ? error : null}
        />
        {activeTasks.length > 0 ? (
          <TaskPanel
            tasks={activeTasks}
            title={t('tasks.activeTitle')}
            className="mt-4"
          />
        ) : null}
        {latestReportOpenState?.status === 'fallback' ? (
          <div
            className={cn(
              'theme-inline-banner theme-inline-banner--warning mt-4 px-4 py-3 transition-colors',
            )}
            data-testid="latest-report-status"
          >
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
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
      </header>

      <div className={cn('workspace-split-layout', hasShellRail && 'workspace-split-layout--main-only')}>
        {!hasShellRail ? (
          <aside className="workspace-split-rail hidden min-h-0 xl:flex xl:max-h-[calc(100vh-6.5rem)] xl:flex-col">
              {sidebarContent}
          </aside>
        ) : null}

        {!hasShellRail && sidebarOpen ? (
          <div className="fixed inset-0 z-40 xl:hidden" onClick={() => setSidebarOpen(false)}>
            <div className="absolute inset-0 home-mobile-overlay" />
            <div
              className="theme-sidebar-shell absolute bottom-0 left-0 top-0 flex w-[min(var(--layout-context-rail-width),88vw)] flex-col overflow-hidden rounded-none rounded-r-[1.35rem] p-3"
              onClick={(event) => event.stopPropagation()}
            >
              {sidebarContent}
            </div>
          </div>
        ) : null}

        <section className="workspace-split-main overflow-x-hidden">
            {error ? (
              <ApiErrorAlert
                error={error}
                className="mb-4"
                onDismiss={clearError}
              />
            ) : null}
            {isLoadingReport ? (
              <div className="flex min-h-[20rem] flex-col items-center justify-center">
                <div className="home-spinner h-10 w-10 animate-spin border-3" />
                <p className="mt-3 text-sm text-secondary-text">{t('home.loadingReport')}</p>
              </div>
            ) : selectedReport ? (
              <div
                ref={resultRegionRef}
                className={selectedReport.details?.standardReport ? 'w-full min-w-0 pb-8' : 'max-w-5xl pb-8'}
              >
                <div key={selectedReport.meta.id ?? selectedReport.meta.queryId} className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                  <ReportSummary data={selectedReport} isHistory />
                </div>
              </div>
            ) : (
              <div className="flex min-h-[22rem] items-center justify-center py-8">
                <div className="theme-panel-solid w-full max-w-4xl rounded-[1.35rem] px-6 py-10 text-center">
                  <div className="theme-panel-subtle mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl">
                    <svg className="h-7 w-7 text-muted-text" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  </div>
                  <h3 className="mb-2 text-lg font-semibold text-foreground">{t('home.emptyTitle')}</h3>
                  <p className="mx-auto max-w-xl text-sm leading-6 text-secondary-text">
                    {t('home.emptyBody')}
                  </p>
                </div>
              </div>
            )}
        </section>
      </div>

      {markdownDrawerOpen && selectedReport?.meta.id ? (
        <ReportMarkdown
          recordId={selectedReport.meta.id}
          stockName={selectedReport.meta.stockName || ''}
          stockCode={selectedReport.meta.stockCode}
          reportLanguage={reportLanguage}
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
          <div className="theme-inline-banner theme-inline-banner--success px-4 py-3 shadow-[0_18px_38px_rgba(0,0,0,0.28)]">
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
