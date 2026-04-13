import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, beforeEach, vi } from 'vitest';
import ScannerPage from '../ScannerPage';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import type {
  ScannerOperationalStatus,
  ScannerRunDetail,
  ScannerRunHistoryResponse,
} from '../../types/scanner';

const {
  getRecentWatchlists,
  getRun,
  getStatus,
  runScan,
  analyzeAsync,
} = vi.hoisted(() => ({
  getRecentWatchlists: vi.fn(),
  getRun: vi.fn(),
  getStatus: vi.fn(),
  runScan: vi.fn(),
  analyzeAsync: vi.fn(),
}));

vi.mock('../../api/scanner', () => ({
  scannerApi: {
    getRecentWatchlists,
    getRun,
    getStatus,
    run: runScan,
  },
}));

vi.mock('../../api/analysis', () => ({
  analysisApi: {
    analyzeAsync,
  },
  DuplicateTaskError: class DuplicateTaskError extends Error {
    stockCode: string;

    existingTaskId: string;

    constructor(stockCode: string, existingTaskId: string, message?: string) {
      super(message || `Duplicate ${stockCode}`);
      this.name = 'DuplicateTaskError';
      this.stockCode = stockCode;
      this.existingTaskId = existingTaskId;
    }
  },
}));

function makeRunDetail(): ScannerRunDetail {
  return {
    id: 101,
    market: 'cn',
    profile: 'cn_preopen_v1',
    profileLabel: 'A股盘前扫描 v1',
    status: 'completed',
    runAt: '2026-04-13T08:30:00',
    completedAt: '2026-04-13T08:31:00',
    watchlistDate: '2026-04-13',
    triggerMode: 'scheduled',
    universeName: 'cn_a_liquid_watchlist_v1',
    shortlistSize: 1,
    universeSize: 300,
    preselectedSize: 60,
    evaluatedSize: 40,
    sourceSummary: 'stock_list=FakeList; snapshot=FakeSnapshot; history=local_first; sector=enabled',
    headline: '今日 A 股盘前优先观察：600001 算力龙头',
    universeNotes: ['剔除 ST 与停牌近似状态。'],
    scoringNotes: ['趋势、量能、活跃度共同决定排序。'],
    diagnostics: {
      historyStats: {
        localHits: 10,
        networkFetches: 5,
      },
      scannerData: {
        universeResolution: {
          source: 'local_universe_cache',
          attempts: [
            { fetcher: 'local_universe_cache', status: 'success', rows: 300 },
          ],
        },
        snapshotResolution: {
          source: 'AkshareFetcher',
          attempts: [
            { fetcher: 'AkshareFetcher', status: 'failed', reasonCode: 'akshare_snapshot_fetch_failed' },
            { fetcher: 'EfinanceFetcher', status: 'success', rows: 4821 },
          ],
        },
        degradedModeUsed: false,
      },
    },
    notification: {
      attempted: true,
      status: 'success',
      success: true,
      channels: ['feishu'],
      message: null,
      reportPath: '/tmp/scanner_watchlist_20260413.md',
      sentAt: '2026-04-13T08:31:20',
    },
    failureReason: null,
    comparisonToPrevious: {
      available: true,
      previousRunId: 100,
      previousWatchlistDate: '2026-04-10',
      newCount: 1,
      retainedCount: 1,
      droppedCount: 1,
      newSymbols: [
        { symbol: '600001', name: '算力龙头', currentRank: 1, previousRank: null, rankDelta: null },
      ],
      retainedSymbols: [
        { symbol: '600002', name: '机器人核心', currentRank: 2, previousRank: 1, rankDelta: -1 },
      ],
      droppedSymbols: [
        { symbol: '600003', name: '稳健白马', currentRank: null, previousRank: 2, rankDelta: null },
      ],
    },
    reviewSummary: {
      available: true,
      reviewWindowDays: 3,
      reviewStatus: 'ready',
      candidateCount: 1,
      reviewedCount: 1,
      pendingCount: 0,
      hitRatePct: 100,
      outperformRatePct: 100,
      avgSameDayCloseReturnPct: 2.4,
      avgReviewWindowReturnPct: 5.8,
      avgMaxFavorableMovePct: 7.2,
      avgMaxAdverseMovePct: -1.9,
      strongCount: 1,
      mixedCount: 0,
      weakCount: 0,
      bestSymbol: '600001',
      bestReturnPct: 5.8,
      weakestSymbol: '600001',
      weakestReturnPct: 5.8,
    },
    shortlist: [
      {
        symbol: '600001',
        name: '算力龙头',
        rank: 1,
        score: 82.4,
        qualityHint: '高优先级',
        reasonSummary: '趋势结构完整，价格站在 MA20/MA60 上方。',
        reasons: ['趋势结构完整，价格站在 MA20/MA60 上方。', '量能活跃，成交额与量比显示资金参与度提升。'],
        keyMetrics: [
          { label: '最新价', value: '18.40' },
          { label: '日涨跌幅', value: '4.2%' },
        ],
        featureSignals: [
          { label: '趋势结构', value: '18.0 / 20' },
          { label: '动量延续', value: '11.0 / 15' },
        ],
        riskNotes: ['接近日内涨停约束，追价容错较低。'],
        watchContext: [
          { label: '观察触发', value: '关注是否上破近 20 日高点 18.55。' },
          { label: '量能确认', value: '优先观察量比维持在 1.2 以上。' },
        ],
        boards: ['AI算力'],
        appearedInRecentRuns: 1,
        lastTradeDate: '2026-04-10',
        scanTimestamp: '2026-04-13T08:30:00',
        realizedOutcome: {
          reviewStatus: 'ready',
          outcomeLabel: 'strong',
          thesisMatch: 'validated',
          reviewWindowDays: 3,
          anchorDate: '2026-04-10',
          windowEndDate: '2026-04-15',
          sameDayCloseReturnPct: 2.4,
          nextDayReturnPct: 1.3,
          reviewWindowReturnPct: 5.8,
          maxFavorableMovePct: 7.2,
          maxAdverseMovePct: -1.9,
          benchmarkCode: '000300',
          benchmarkReturnPct: 1.7,
          outperformedBenchmark: true,
        },
        diagnostics: {
          historySource: 'local_db',
          componentScores: { trend: 18.0 },
        },
      },
    ],
  };
}

function makeHistoryResponse(): ScannerRunHistoryResponse {
  return {
    total: 1,
    page: 1,
    limit: 6,
    items: [
      {
        id: 101,
        market: 'cn',
        profile: 'cn_preopen_v1',
        profileLabel: 'A股盘前扫描 v1',
        status: 'completed',
        runAt: '2026-04-13T08:30:00',
        completedAt: '2026-04-13T08:31:00',
        watchlistDate: '2026-04-13',
        triggerMode: 'scheduled',
        universeName: 'cn_a_liquid_watchlist_v1',
        shortlistSize: 1,
        universeSize: 300,
        preselectedSize: 60,
        evaluatedSize: 40,
        sourceSummary: 'test',
        headline: '今日 A 股盘前优先观察：600001 算力龙头',
        topSymbols: ['600001'],
        notificationStatus: 'success',
        failureReason: null,
        changeSummary: {
          available: true,
          previousRunId: 100,
          previousWatchlistDate: '2026-04-10',
          newCount: 1,
          retainedCount: 0,
          droppedCount: 1,
          newSymbols: [
            { symbol: '600001', name: '算力龙头', currentRank: 1, previousRank: null, rankDelta: null },
          ],
          retainedSymbols: [],
          droppedSymbols: [
            { symbol: '600003', name: '稳健白马', currentRank: null, previousRank: 1, rankDelta: null },
          ],
        },
        reviewSummary: {
          available: true,
          reviewWindowDays: 3,
          reviewStatus: 'ready',
          candidateCount: 1,
          reviewedCount: 1,
          pendingCount: 0,
          hitRatePct: 100,
          outperformRatePct: 100,
          avgSameDayCloseReturnPct: 2.4,
          avgReviewWindowReturnPct: 5.8,
          avgMaxFavorableMovePct: 7.2,
          avgMaxAdverseMovePct: -1.9,
          strongCount: 1,
          mixedCount: 0,
          weakCount: 0,
          bestSymbol: '600001',
          bestReturnPct: 5.8,
          weakestSymbol: '600001',
          weakestReturnPct: 5.8,
        },
      },
    ],
  };
}

function makeStatusResponse(): ScannerOperationalStatus {
  return {
    market: 'cn',
    profile: 'cn_preopen_v1',
    profileLabel: 'A股盘前扫描 v1',
    watchlistDate: '2026-04-13',
    todayTradingDay: true,
    scheduleEnabled: true,
    scheduleTime: '08:40',
    scheduleRunImmediately: false,
    notificationEnabled: true,
    todayWatchlist: {
      id: 101,
      watchlistDate: '2026-04-13',
      triggerMode: 'scheduled',
      status: 'completed',
      runAt: '2026-04-13T08:30:00',
      headline: '今日 A 股盘前优先观察：600001 算力龙头',
      shortlistSize: 1,
      notificationStatus: 'success',
      failureReason: null,
    },
    lastRun: {
      id: 101,
      watchlistDate: '2026-04-13',
      triggerMode: 'scheduled',
      status: 'completed',
      runAt: '2026-04-13T08:30:00',
      headline: '今日 A 股盘前优先观察：600001 算力龙头',
      shortlistSize: 1,
      notificationStatus: 'success',
      failureReason: null,
    },
    lastScheduledRun: {
      id: 101,
      watchlistDate: '2026-04-13',
      triggerMode: 'scheduled',
      status: 'completed',
      runAt: '2026-04-13T08:30:00',
      headline: '今日 A 股盘前优先观察：600001 算力龙头',
      shortlistSize: 1,
      notificationStatus: 'success',
      failureReason: null,
    },
    lastManualRun: {
      id: 100,
      watchlistDate: '2026-04-12',
      triggerMode: 'manual',
      status: 'completed',
      runAt: '2026-04-12T08:35:00',
      headline: '昨日手动观察名单',
      shortlistSize: 1,
      notificationStatus: 'not_attempted',
      failureReason: null,
    },
    latestFailure: null,
    qualitySummary: {
      available: true,
      reviewWindowDays: 3,
      benchmarkCode: '000300',
      runCount: 5,
      reviewedRunCount: 4,
      reviewedCandidateCount: 16,
      reviewCoveragePct: 80,
      avgCandidatesPerRun: 4.2,
      avgShortlistReturnPct: 1.9,
      positiveRunRatePct: 75,
      hitRatePct: 62.5,
      outperformRatePct: 56.3,
      positiveCandidateAvgScore: 83.1,
      negativeCandidateAvgScore: 74.8,
    },
  };
}

function renderScannerPage() {
  return render(
    <UiLanguageProvider>
      <MemoryRouter initialEntries={['/scanner']}>
        <Routes>
          <Route path="/scanner" element={<ScannerPage />} />
          <Route path="/" element={<div>Home Landing</div>} />
          <Route path="/backtest" element={<div>Backtest Landing</div>} />
        </Routes>
      </MemoryRouter>
    </UiLanguageProvider>,
  );
}

describe('ScannerPage', () => {
  beforeEach(() => {
    getRecentWatchlists.mockReset();
    getRun.mockReset();
    getStatus.mockReset();
    runScan.mockReset();
    analyzeAsync.mockReset();

    getRecentWatchlists.mockResolvedValue(makeHistoryResponse());
    getRun.mockResolvedValue(makeRunDetail());
    getStatus.mockResolvedValue(makeStatusResponse());
    runScan.mockResolvedValue(makeRunDetail());
    analyzeAsync.mockResolvedValue({ taskId: 'task-1' });
  });

  it('renders today watchlist status, recent watchlists, and opens the detail drawer', async () => {
    renderScannerPage();

    expect((await screen.findAllByText('算力龙头')).length).toBeGreaterThan(0);
    expect(screen.getByText('AI算力')).toBeInTheDocument();
    expect(screen.getAllByText('2026-04-13').length).toBeGreaterThan(0);
    expect(screen.getAllByText('推送成功').length).toBeGreaterThan(0);
    expect(screen.getAllByText('定时').length).toBeGreaterThan(0);
    expect(screen.getByText('跨日对比')).toBeInTheDocument();
    expect(screen.getByText('盘后复盘')).toBeInTheDocument();
    expect(screen.getByText('近期质量')).toBeInTheDocument();
    expect(screen.getAllByText('新入选 1').length).toBeGreaterThan(0);
    expect(screen.getAllByText('逻辑已验证').length).toBeGreaterThan(0);
    expect(screen.getByText('运行时诊断')).toBeInTheDocument();
    expect(screen.getAllByText(/local_universe_cache/).length).toBeGreaterThan(0);
    expect(screen.getByText(/akshare_snapshot_fetch_failed/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '查看解释' }));

    expect(await screen.findByText('入选原因')).toBeInTheDocument();
    expect(screen.getByText('当日收盘')).toBeInTheDocument();
    expect(screen.getByText('诊断信息')).toBeInTheDocument();
  });

  it('runs the scanner and renders the returned shortlist', async () => {
    getRecentWatchlists.mockResolvedValueOnce({
      total: 0,
      page: 1,
      limit: 6,
      items: [],
    });
    getStatus.mockResolvedValueOnce({
      ...makeStatusResponse(),
      todayWatchlist: null,
      lastRun: null,
      lastScheduledRun: null,
      lastManualRun: null,
    });

    renderScannerPage();

    expect(await screen.findByText('准备生成今日 shortlist')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '运行扫描' }));

    await waitFor(() => {
      expect(runScan).toHaveBeenCalledWith({
        market: 'cn',
        profile: 'cn_preopen_v1',
        shortlistSize: 5,
        universeLimit: 300,
        detailLimit: 60,
      });
    });
    expect((await screen.findAllByText('算力龙头')).length).toBeGreaterThan(0);
  });

  it('starts deeper analysis from a shortlist candidate', async () => {
    renderScannerPage();

    expect((await screen.findAllByText('算力龙头')).length).toBeGreaterThan(0);
    expect(await screen.findByRole('button', { name: '深入分析' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '深入分析' }));

    await waitFor(() => {
      expect(analyzeAsync).toHaveBeenCalledWith({
        stockCode: '600001',
        stockName: '算力龙头',
        originalQuery: '600001',
        selectionSource: 'manual',
      });
    });

    expect(await screen.findByText('Home Landing')).toBeInTheDocument();
  });

  it('navigates to backtest from a shortlist candidate action', async () => {
    renderScannerPage();

    expect((await screen.findAllByText('算力龙头')).length).toBeGreaterThan(0);
    expect(await screen.findByRole('button', { name: '去回测' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '去回测' }));

    expect(await screen.findByText('Backtest Landing')).toBeInTheDocument();
  });
});
