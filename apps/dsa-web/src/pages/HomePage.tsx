import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiErrorAlert, ConfirmDialog, Button } from '../components/common';
import { StockAutocomplete } from '../components/StockAutocomplete';
import { HistoryList } from '../components/history';
import { ReportMarkdown, ReportSummary } from '../components/report';
import { TaskPanel } from '../components/tasks';
import { useShellRail } from '../components/layout/ShellRailContext';
import { useDashboardLifecycle } from '../hooks';
import { useStockPoolStore } from '../stores';
import { getReportText, normalizeReportLanguage } from '../utils/reportLanguage';

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const { setRailContent, closeMobileRail, isConnected: hasShellRail } = useShellRail();

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
    syncTaskCreated,
    syncTaskUpdated,
    syncTaskFailed,
    removeTask,
    openMarkdownDrawer,
    closeMarkdownDrawer,
  } = useStockPoolStore((state) => state);

  useEffect(() => {
    document.title = '每日选股分析 - DSA';
  }, []);
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

  const selectedIds = useMemo(() => new Set(selectedHistoryIds), [selectedHistoryIds]);

  const sidebarContent = useMemo(
    () => (
      <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-[1.2rem] border border-white/7 bg-[#050505]">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <HistoryList
            items={historyItems}
            isLoading={isLoadingHistory}
            isLoadingMore={isLoadingMore}
            hasMore={hasMore}
            selectedId={selectedReport?.meta.id}
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
            className="flex-1 overflow-hidden"
            embedded
          />
          <TaskPanel tasks={activeTasks} embedded className="border-t border-white/7" />
        </div>
      </div>
    ),
    [
      activeTasks,
      hasMore,
      historyItems,
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

  return (
    <div
      data-testid="home-dashboard"
      className="flex h-[calc(100vh-5rem)] w-full flex-col overflow-hidden bg-[#020202] md:flex-row sm:h-[calc(100vh-5.5rem)] lg:h-[calc(100vh-2rem)]"
    >
      <div className="flex min-w-0 w-full flex-1 flex-col">
        <header className="flex-shrink-0 px-3 pb-3 pt-3 md:px-4 lg:px-6 xl:px-8">
          <div className="overflow-hidden rounded-[1.5rem] border border-white/8 bg-white/[0.04] px-4 py-4 shadow-[0_18px_48px_rgba(0,0,0,0.24)] backdrop-blur-xl md:px-5 lg:px-6">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">DSA Market Terminal</p>
                <h1 className="mt-2 text-xl font-semibold tracking-tight text-foreground md:text-2xl">深黑终端式股票分析工作台</h1>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-secondary-text">
                  输入股票代码后直接查看结构化报告，核心信息优先展示，剩余模块按自然阅读顺序向下展开。
                </p>
              </div>
              {!hasShellRail ? (
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="xl:hidden -mr-1 flex-shrink-0 rounded-xl border border-white/8 bg-white/[0.04] p-2 text-secondary-text transition-colors hover:bg-white/[0.06] hover:text-foreground"
                  title="历史记录"
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
                      placeholder="输入股票代码或名称，如 600519、贵州茅台、AAPL"
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
                        分析中
                      </>
                    ) : (
                      '分析'
                    )}
                  </button>
                </div>
                {inputError ? (
                  <p className="text-xs text-danger">{inputError}</p>
                ) : null}
                {duplicateError ? (
                  <p className="text-xs text-warning">{duplicateError}</p>
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
                    追问 AI
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
                    {reportText.fullReport}
                  </Button>
                </div>
              ) : null}
            </div>
          </div>
        </header>

        <div className="flex min-h-0 flex-1 overflow-hidden">
          {!hasShellRail ? (
            <div className="hidden min-h-0 w-[20rem] shrink-0 flex-col overflow-hidden px-3 pb-4 xl:flex xl:w-[21rem] xl:px-4">
              {sidebarContent}
            </div>
          ) : null}

          {!hasShellRail && sidebarOpen ? (
            <div className="fixed inset-0 z-40 xl:hidden" onClick={() => setSidebarOpen(false)}>
              <div className="absolute inset-0 home-mobile-overlay" />
              <div
                className="absolute bottom-0 left-0 top-0 flex w-[19rem] flex-col overflow-hidden rounded-none rounded-r-[1.35rem] border-r border-white/8 bg-[#050505] p-3 shadow-[0_24px_56px_rgba(0,0,0,0.42)]"
                onClick={(event) => event.stopPropagation()}
              >
                {sidebarContent}
              </div>
            </div>
          ) : null}

          <section className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto px-3 pb-6 md:px-4 lg:px-6 xl:px-8">
            {error ? (
              <ApiErrorAlert
                error={error}
                className="mb-4"
                onDismiss={clearError}
              />
            ) : null}
            {isLoadingReport ? (
              <div className="flex h-full flex-col items-center justify-center">
                <div className="home-spinner h-10 w-10 animate-spin border-3" />
                <p className="mt-3 text-sm text-secondary-text">加载报告中...</p>
              </div>
            ) : selectedReport ? (
              <div className={selectedReport.details?.standardReport ? 'w-full min-w-0 pb-8' : 'max-w-5xl pb-8'}>
                <div key={selectedReport.meta.id ?? selectedReport.meta.queryId} className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                  <ReportSummary data={selectedReport} isHistory />
                </div>
              </div>
            ) : (
              <div className="flex h-full items-center justify-center py-8">
                <div className="w-full max-w-4xl rounded-[1.35rem] border border-white/8 bg-[#050505] px-6 py-10 text-center shadow-[0_18px_42px_rgba(0,0,0,0.26)]">
                  <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/8 bg-white/[0.04]">
                    <svg className="h-7 w-7 text-muted-text" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  </div>
                  <h3 className="mb-2 text-lg font-semibold text-foreground">开始分析</h3>
                  <p className="mx-auto max-w-xl text-sm leading-6 text-secondary-text">
                    输入股票代码进行分析，或从左侧历史列表中选择已有报告。主内容区会按总览、行情、技术、基本面、财报和作战计划顺序展开。
                  </p>
                </div>
              </div>
            )}
          </section>
        </div>
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
        title="删除历史记录"
        message={
          selectedHistoryIds.length === 1
            ? '确认删除这条历史记录吗？删除后将不可恢复。'
            : `确认删除选中的 ${selectedHistoryIds.length} 条历史记录吗？删除后将不可恢复。`
        }
        confirmText={isDeletingHistory ? '删除中...' : '确认删除'}
        cancelText="取消"
        isDanger={true}
        onConfirm={() => {
          void deleteSelectedHistory();
          setShowDeleteConfirm(false);
        }}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </div>
  );
};

export default HomePage;
