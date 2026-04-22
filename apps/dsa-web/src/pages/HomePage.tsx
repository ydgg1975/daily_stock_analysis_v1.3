import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ApiErrorAlert, ConfirmDialog, Button, EmptyState, InlineAlert } from '../components/common';
import { AppPage } from '../components/common/AppPage';
import { DashboardStateBlock } from '../components/dashboard';
import { StockAutocomplete } from '../components/StockAutocomplete';
import { HistoryList } from '../components/history';
import { ReportMarkdown, ReportSummary } from '../components/report';
import { ChatDrawer } from '../components/chat';
import { ShareButton } from '../components/share/ShareButton';
import { watchlistApi } from '../api/watchlist';
import { useDashboardLifecycle, useHomeDashboardState } from '../hooks';
import { getReportText, normalizeReportLanguage } from '../utils/reportLanguage';
import type { AnalysisReport, TaskInfo } from '../types/analysis';

// ── Analyzing placeholder skeleton (no report yet, task in progress) ─────────
function AnalyzingPlaceholder({ task }: { task: TaskInfo }) {
  const progress = Math.max(0, Math.min(100, task.progress ?? 0));
  return (
    <div className="max-w-3xl space-y-4 pb-8 animate-fade-in">
      {/* Header: stock identity skeleton */}
      <div className="terminal-card rounded-2xl p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-2 flex-1">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan animate-pulse" />
              <span className="text-xs font-medium text-cyan">正在分析</span>
              <span className="text-sm font-semibold text-foreground">
                {task.stockName || task.stockCode}
              </span>
            </div>
            {task.message && (
              <p className="text-xs text-secondary-text">{task.message}</p>
            )}
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/6">
              <div
                className="h-full rounded-full bg-cyan/70 transition-[width] duration-500 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
          {/* Sentiment gauge skeleton */}
          <div className="shrink-0 flex h-12 w-12 items-center justify-center rounded-full border border-white/8 bg-white/4">
            <div className="h-6 w-6 animate-pulse rounded-full bg-cyan/20" />
          </div>
        </div>
        {/* Summary skeleton lines */}
        <div className="space-y-2 pt-1">
          <div className="h-3 w-full animate-pulse rounded-full bg-white/6" />
          <div className="h-3 w-5/6 animate-pulse rounded-full bg-white/6" />
          <div className="h-3 w-4/6 animate-pulse rounded-full bg-white/5" />
        </div>
      </div>

      {/* K-line chart skeleton */}
      <div className="terminal-card rounded-2xl p-4">
        <div className="mb-3 h-3 w-16 animate-pulse rounded-full bg-white/6" />
        <div className="h-[200px] animate-pulse rounded-xl bg-white/4" />
      </div>

      {/* Strategy skeleton */}
      <div className="terminal-card rounded-2xl p-5">
        <div className="mb-3 h-3 w-20 animate-pulse rounded-full bg-white/6" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="rounded-xl border border-white/6 bg-white/3 p-3 space-y-2">
              <div className="h-2.5 w-10 animate-pulse rounded-full bg-white/6" />
              <div className="h-5 w-16 animate-pulse rounded-full bg-white/8" />
            </div>
          ))}
        </div>
      </div>

      {/* News skeleton */}
      <div className="terminal-card rounded-2xl p-5 space-y-3">
        <div className="h-3 w-16 animate-pulse rounded-full bg-white/6" />
        {[1, 2, 3].map((i) => (
          <div key={i} className="space-y-1.5">
            <div className="h-3 w-full animate-pulse rounded-full bg-white/6" />
            <div className="h-2.5 w-3/4 animate-pulse rounded-full bg-white/4" />
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Analyzing banner (shown above report when tasks are running) ──────────────
function AnalyzingBanner({ tasks }: { tasks: TaskInfo[] }) {
  const active = tasks.filter((t) => t.status === 'pending' || t.status === 'processing');
  if (active.length === 0) return null;

  return (
    <div className="space-y-2">
      {active.map((task) => {
        const progress = Math.max(0, Math.min(100, task.progress ?? 0));
        const isProcessing = task.status === 'processing';
        return (
          <div
            key={task.taskId}
            className="rounded-xl border border-cyan/25 bg-cyan/5 px-4 py-3"
          >
            <div className="mb-2 flex items-center gap-2">
              <span
                className={`h-1.5 w-1.5 rounded-full bg-cyan ${isProcessing ? 'animate-pulse' : ''}`}
              />
              <span className="text-xs font-medium text-cyan">
                {isProcessing ? '正在分析' : '等待中'}
              </span>
              <span className="text-xs font-medium text-foreground">
                {task.stockName || task.stockCode}
              </span>
              {task.message && (
                <span className="min-w-0 flex-1 truncate text-xs text-muted-text">
                  · {task.message}
                </span>
              )}
              <span className="ml-auto shrink-0 font-mono text-[11px] text-muted-text">
                {progress}%
              </span>
            </div>
            <div className="h-1 overflow-hidden rounded-full bg-white/6">
              <div
                className="h-full rounded-full bg-cyan/80 transition-[width] duration-500 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Strip strategy explanations, keep only the price token (e.g. "725.00元")
function extractPrice(value: string): string {
  return value.split('（')[0].split('(')[0].trim();
}

// ── Market sentiment panel (right column) ────────────────────────────────────
function MarketSentimentPanel({ report }: { report: AnalysisReport | null }) {
  const score = report?.summary?.sentimentScore;
  const scoreColor =
    score == null
      ? 'text-muted-text'
      : score >= 60
        ? 'text-cyan'
        : score >= 40
          ? 'text-purple'
          : 'text-danger';

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto">
      <p className="text-xs uppercase tracking-wider text-secondary-text">市场情绪</p>

      {report ? (
        <>
          {/* Sentiment score */}
          <div className="terminal-card rounded-2xl p-4">
            <p className="mb-2 text-xs text-muted-text">个股情绪</p>
            <div className="flex items-end gap-1.5">
              <span className={`font-mono text-3xl font-bold ${scoreColor}`}>
                {score ?? '--'}
              </span>
              <span className="mb-0.5 text-xs text-muted-text">/ 100</span>
            </div>
            {report.summary?.sentimentLabel && (
              <p className="mt-1 text-xs text-secondary-text">{report.summary.sentimentLabel}</p>
            )}
          </div>

          {/* Operation advice */}
          {report.summary?.operationAdvice && (
            <div className="terminal-card rounded-2xl p-4">
              <p className="mb-2 text-xs text-muted-text">操作建议</p>
              <span className="rounded-full border border-cyan/30 bg-cyan/10 px-3 py-0.5 text-sm font-medium text-cyan">
                {report.summary.operationAdvice}
              </span>
            </div>
          )}

          {/* Strategy points */}
          {report.strategy && (
            <div className="terminal-card rounded-2xl p-4">
              <p className="mb-2 text-xs text-muted-text">策略点位</p>
              <div className="space-y-2">
                {[
                  { label: '首选买入', value: report.strategy.idealBuy, color: 'text-danger' },
                  { label: '次选买入', value: report.strategy.secondaryBuy, color: 'text-danger/70' },
                  { label: '止损', value: report.strategy.stopLoss, color: 'text-success' },
                  { label: '目标价', value: report.strategy.takeProfit, color: 'text-cyan' },
                ]
                  .filter((s) => s.value != null)
                  .map((s) => (
                    <div key={s.label} className="flex items-center justify-between text-xs">
                      <span className="text-muted-text">{s.label}</span>
                      <span className={`font-mono font-semibold ${s.color}`}>{extractPrice(s.value!)}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="terminal-card rounded-2xl p-4 text-center">
          <p className="text-xs text-muted-text">选择报告后查看</p>
        </div>
      )}

      {/* Placeholder for future market-level sentiment */}
      <div className="terminal-card rounded-2xl p-4 opacity-40">
        <p className="mb-1 text-xs text-muted-text">大盘情绪</p>
        <p className="text-xs text-muted-text">即将支持</p>
      </div>
    </div>
  );
}

const HomePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [watchlistCodes, setWatchlistCodes] = useState<Set<string>>(new Set());
  const [chatDrawerOpen, setChatDrawerOpen] = useState(false);

  const {
    query,
    inputError,
    duplicateError,
    error,
    isAnalyzing,
    historyItems,
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
    loadMoreHistory,
    selectHistoryItem,
    toggleHistorySelection,
    toggleSelectAllVisible,
    deleteSelectedHistory,
    submitAnalysis,
    notify,
    setNotify,
    syncTaskCreated,
    syncTaskUpdated,
    syncTaskFailed,
    removeTask,
    openMarkdownDrawer,
    closeMarkdownDrawer,
    selectedIds,
  } = useHomeDashboardState();

  useEffect(() => {
    document.title = '每日选股分析 - DSA';
  }, []);

  // When navigated here with ?q= (e.g., from watchlist card):
  // - default: pre-fill input and show the most recent history record for that stock.
  // - ?force=1: immediately trigger a fresh analysis (force_refresh=true).
  const pendingQRef = useRef<string | null>(null);
  const didSelectQRef = useRef(false);

  useEffect(() => {
    if (pendingQRef.current !== null) return;
    const q = searchParams.get('q');
    if (!q) return;
    const force = searchParams.get('force') === '1';
    setSearchParams({}, { replace: true });
    setQuery(q);
    pendingQRef.current = q;
    if (force) {
      // Skip the history-select path and trigger a fresh analysis.
      didSelectQRef.current = true;
      pendingQRef.current = null;
      void submitAnalysis({
        stockCode: q,
        originalQuery: q,
        selectionSource: 'manual',
        forceRefresh: true,
      });
    }
  }, [searchParams, setSearchParams, setQuery, submitAnalysis]);

  // Once history has loaded, find and select the most recent record for the target stock
  useEffect(() => {
    if (didSelectQRef.current) return;
    const q = pendingQRef.current;
    if (!q || isLoadingHistory) return;
    const match = historyItems.find((item) => item.stockCode === q);
    if (match?.id != null) {
      didSelectQRef.current = true;
      pendingQRef.current = null;
      void selectHistoryItem(match.id);
    }
    // No history found: input is pre-filled; user can click "分析" manually
  }, [historyItems, isLoadingHistory, selectHistoryItem]);
  const reportLanguage = normalizeReportLanguage(selectedReport?.meta.reportLanguage);
  const reportText = getReportText(reportLanguage);

  useDashboardLifecycle({
    loadInitialHistory,
    refreshHistory,
    syncTaskCreated,
    syncTaskUpdated,
    syncTaskFailed,
    removeTask,
  });

  const handleHistoryItemClick = useCallback((recordId: number) => {
    void selectHistoryItem(recordId);
    setSidebarOpen(false);
  }, [selectHistoryItem]);

  const handleSubmitAnalysis = useCallback(
    (
      stockCode?: string,
      stockName?: string,
      selectionSource?: 'manual' | 'autocomplete' | 'import' | 'image',
    ) => {
      void submitAnalysis({
        stockCode,
        stockName,
        originalQuery: query,
        selectionSource: selectionSource ?? 'manual',
      });
    },
    [query, submitAnalysis],
  );

  const handleAskFollowUp = useCallback(() => {
    if (selectedReport?.meta.id === undefined) {
      return;
    }
    setChatDrawerOpen(true);
  }, [selectedReport]);

  const handleCloseChatDrawer = useCallback(() => {
    setChatDrawerOpen(false);
  }, []);

  const handleDeleteSelectedHistory = useCallback(() => {
    void deleteSelectedHistory();
    setShowDeleteConfirm(false);
  }, [deleteSelectedHistory]);

  // Load watchlist codes for star toggle on history items
  useEffect(() => {
    watchlistApi.list().then((items) => {
      setWatchlistCodes(new Set(items.map((i) => i.stockCode)));
    }).catch(() => undefined);
  }, []);

  const handleToggleWatchlist = useCallback(
    async (stockCode: string, stockName: string | undefined, inWatchlist: boolean) => {
      if (inWatchlist) {
        await watchlistApi.remove(stockCode).catch(() => undefined);
        setWatchlistCodes((prev) => { const next = new Set(prev); next.delete(stockCode); return next; });
      } else {
        await watchlistApi.add(stockCode, stockName).catch(() => undefined);
        setWatchlistCodes((prev) => new Set(prev).add(stockCode));
      }
    },
    [],
  );

  const sidebarContent = useMemo(
    () => (
      <div className="flex min-h-0 h-full flex-col gap-3 overflow-hidden">
        <HistoryList
          items={historyItems}
          isLoading={isLoadingHistory}
          isLoadingMore={isLoadingMore}
          hasMore={hasMore}
          selectedId={selectedReport?.meta.id}
          selectedIds={selectedIds}
          isDeleting={isDeletingHistory}
          onItemClick={handleHistoryItemClick}
          onLoadMore={() => void loadMoreHistory()}
          onToggleItemSelection={toggleHistorySelection}
          onToggleSelectAll={toggleSelectAllVisible}
          onDeleteSelected={() => setShowDeleteConfirm(true)}
          className="flex-1 overflow-hidden"
          watchlistCodes={watchlistCodes}
          onToggleWatchlist={(stockCode, stockName, inWatchlist) => {
            void handleToggleWatchlist(stockCode, stockName, inWatchlist);
          }}
        />
      </div>
    ),
    [
      hasMore,
      historyItems,
      isDeletingHistory,
      isLoadingHistory,
      isLoadingMore,
      handleHistoryItemClick,
      handleToggleWatchlist,
      loadMoreHistory,
      selectedIds,
      selectedReport?.meta.id,
      toggleHistorySelection,
      toggleSelectAllVisible,
      watchlistCodes,
    ],
  );

  return (
    <AppPage className="flex min-h-full flex-col px-0 pb-0 pt-0 md:px-0 lg:px-0">
    <div
      data-testid="home-dashboard"
      className="flex h-full w-full flex-col overflow-hidden"
    >
      {/* ── Full-width search header (all three columns align below) ── */}
      <header className="flex min-w-0 shrink-0 items-center gap-2.5 overflow-hidden border-b border-subtle/60 px-3 py-3 md:px-4">
        <button
          onClick={() => setSidebarOpen(true)}
          className="md:hidden -ml-1 shrink-0 rounded-lg p-1.5 text-secondary-text transition-colors hover:bg-hover hover:text-foreground"
          aria-label="历史记录"
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <div className="relative min-w-0 flex-1">
          <StockAutocomplete
            value={query}
            onChange={setQuery}
            onSubmit={(stockCode, stockName, selectionSource) => {
              handleSubmitAnalysis(stockCode, stockName, selectionSource);
            }}
            placeholder="输入股票代码或名称，如 600519、贵州茅台、AAPL"
            disabled={isAnalyzing}
            className={inputError ? 'border-danger/50' : undefined}
          />
        </div>
        <label className="flex h-10 shrink-0 cursor-pointer items-center gap-1.5 rounded-xl border border-subtle bg-surface/60 px-3 text-xs text-secondary-text select-none transition-colors hover:border-subtle-hover hover:text-foreground">
          <input
            type="checkbox"
            checked={notify}
            onChange={(e) => setNotify(e.target.checked)}
            className="h-3.5 w-3.5 rounded border-border accent-primary"
          />
          推送通知
        </label>
        <button
          type="button"
          onClick={() => handleSubmitAnalysis()}
          disabled={!query || isAnalyzing}
          className="btn-primary flex h-10 shrink-0 items-center gap-1.5 whitespace-nowrap"
        >
          {isAnalyzing ? (
            <>
              <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              分析中
            </>
          ) : (
            '分析'
          )}
        </button>
      </header>

      {inputError || duplicateError ? (
        <div className="shrink-0 px-3 pt-2 md:px-4">
          {inputError ? (
            <InlineAlert variant="danger" title="输入有误" message={inputError} className="rounded-xl px-3 py-2 text-xs shadow-none" />
          ) : null}
          {!inputError && duplicateError ? (
            <InlineAlert variant="warning" title="任务已存在" message={duplicateError} className="rounded-xl px-3 py-2 text-xs shadow-none" />
          ) : null}
        </div>
      ) : null}

      {/* ── Three-column body ─────────────────────────────────────── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* Left column: analysis history */}
        <aside className="hidden md:flex w-64 lg:w-72 shrink-0 flex-col overflow-hidden border-r border-subtle/60 p-3">
          {sidebarContent}
        </aside>

        {/* Mobile history drawer */}
        {sidebarOpen ? (
          <div className="fixed inset-0 z-40 md:hidden" onClick={() => setSidebarOpen(false)}>
            <div className="page-drawer-overlay absolute inset-0" />
            <div
              className="dashboard-card absolute bottom-0 left-0 top-0 flex w-72 flex-col overflow-hidden !rounded-none !rounded-r-xl p-3 shadow-2xl"
              onClick={(event) => event.stopPropagation()}
            >
              {sidebarContent}
            </div>
          </div>
        ) : null}

        {/* Middle column */}
        <div className="flex-1 flex min-h-0 min-w-0 flex-col overflow-hidden">

          {/* ── Banner + action buttons on the same row ── */}
          {(activeTasks.length > 0 || selectedReport) && (
            <div className="flex shrink-0 items-center gap-3 border-b border-subtle/60 px-3 py-2 md:px-4">
              {activeTasks.length > 0 && (
                <div className="min-w-0 flex-1">
                  <AnalyzingBanner tasks={activeTasks} />
                </div>
              )}
              {selectedReport && (
                <div className="flex shrink-0 items-center gap-2 ml-auto">
                  <Button
                    variant="home-action-ai"
                    size="sm"
                    disabled={selectedReport.meta.id === undefined}
                    onClick={handleAskFollowUp}
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                    追问 AI
                  </Button>
                  <Button
                    variant="home-action-ai"
                    size="sm"
                    disabled={selectedReport.meta.id === undefined}
                    onClick={openMarkdownDrawer}
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    {reportText.fullReport}
                  </Button>
                  {selectedReport.meta.id !== undefined && (
                    <ShareButton analysisHistoryId={selectedReport.meta.id} />
                  )}
                </div>
              )}
            </div>
          )}

          {/* Report / placeholder / empty */}
          <section className="flex-1 min-h-0 overflow-y-auto px-3 pb-4 pt-3 md:px-4 touch-pan-y">
            {error ? (
              <ApiErrorAlert error={error} className="mb-3" onDismiss={clearError} />
            ) : null}

            {isLoadingReport ? (
              <div className="flex h-full flex-col items-center justify-center">
                <DashboardStateBlock title="加载报告中..." loading />
              </div>
            ) : selectedReport ? (
              <div className="max-w-3xl space-y-4 pb-8">
                <ReportSummary data={selectedReport} isHistory />
              </div>
            ) : activeTasks.length > 0 ? (
              <AnalyzingPlaceholder task={activeTasks[0]} />
            ) : (
              <div className="flex h-full items-center justify-center">
                <EmptyState
                  title="开始分析"
                  description="输入股票代码进行分析，或从左侧选择历史报告查看。"
                  className="max-w-xl border-dashed"
                  icon={(
                    <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  )}
                />
              </div>
            )}
          </section>
        </div>

        {/* Right column: market sentiment */}
        <aside className="hidden xl:flex w-60 2xl:w-72 shrink-0 flex-col overflow-hidden border-l border-subtle/60 p-3">
          <MarketSentimentPanel report={selectedReport} />
        </aside>
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

      <ChatDrawer
        isOpen={chatDrawerOpen}
        onClose={handleCloseChatDrawer}
        report={chatDrawerOpen ? selectedReport : null}
      />

      <ConfirmDialog
        isOpen={showDeleteConfirm}
        title="删除历史记录"
        message={
          selectedHistoryIds.length === 1
            ? '确认删除这条历史记录吗？删除后将不可恢复。'
            : `确认删除选中的 ${selectedHistoryIds.length} 条历史记录吗？删除后将不可恢复。`
        }
        confirmText={isDeletingHistory ? '删除中...' : '确认删除'}
        cancelText="取消"
        isDanger={true}
        onConfirm={handleDeleteSelectedHistory}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </div>
    </AppPage>
  );
};

export default HomePage;
