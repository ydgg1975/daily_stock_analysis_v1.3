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
  getRuns,
  getRun,
  getStatus,
  runScan,
  analyzeAsync,
} = vi.hoisted(() => ({
  getRecentWatchlists: vi.fn(),
  getRuns: vi.fn(),
  getRun: vi.fn(),
  getStatus: vi.fn(),
  runScan: vi.fn(),
  analyzeAsync: vi.fn(),
}));

vi.mock('../../api/scanner', () => ({
  scannerApi: {
    getRecentWatchlists,
    getRuns,
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
      coverageSummary: {
        inputUniverseSize: 300,
        eligibleAfterUniverseFetch: 182,
        eligibleAfterLiquidityFilter: 60,
        eligibleAfterDataAvailabilityFilter: 40,
        rankedCandidateCount: 40,
        shortlistedCount: 1,
        excludedTotal: 260,
        excludedByReason: [
          { reason: 'filtered_by_profile_constraints', label: 'Profile filters', count: 240 },
          { reason: 'missing_history', label: 'Missing history', count: 20 },
        ],
        likelyBottleneck: 'filtering',
        likelyBottleneckLabel: '多数标的在 profile / liquidity 过滤阶段被淘汰',
      },
      providerDiagnostics: {
        configuredPrimaryProvider: 'AkshareFetcher',
        providersUsed: ['AkshareFetcher', 'EfinanceFetcher', 'FakeDailySource'],
        quoteSourceUsed: 'EfinanceFetcher',
        snapshotSourceUsed: 'EfinanceFetcher',
        historySourceUsed: 'local_db',
        fallbackOccurred: true,
        fallbackCount: 1,
        providerFailureCount: 1,
        missingDataSymbolCount: 20,
        providerWarnings: ['AkshareFetcher snapshot failed, switched to EfinanceFetcher'],
      },
      historyStats: {
        localHits: 10,
        networkFetches: 5,
      },
      aiInterpretation: {
        enabled: true,
        status: 'completed',
        topN: 1,
        attemptedCandidates: 1,
        generatedCandidates: 1,
        failedCandidates: 0,
        skippedCandidates: 0,
        modelsUsed: ['gemini/gemini-2.5-flash'],
        fallbackUsed: false,
        message: '已为前 1 名候选生成 AI 解读。',
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
        aiInterpretation: {
          available: true,
          status: 'generated',
          summary: 'AI 认为这更像趋势延续中的临界突破，今天值得优先看竞价和开盘量能。',
          opportunityType: '临界突破',
          riskInterpretation: '若竞价一步到位高开过多，容易演变成冲高回落。',
          watchPlan: '盘前先看竞价承接，开盘后确认量比是否继续维持在强势区间。',
          reviewCommentary: '后续表现跑赢基准，说明趋势与板块共振成立。',
          provider: 'gemini',
          model: 'gemini/gemini-2.5-flash',
          generatedAt: '2026-04-13T08:30:10',
          message: null,
        },
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

function makeUsRunDetail(): ScannerRunDetail {
  return {
    ...makeRunDetail(),
    id: 202,
    market: 'us',
    profile: 'us_preopen_v1',
    profileLabel: 'US Pre-open Scanner v1',
    runAt: '2026-04-13T21:20:00',
    completedAt: '2026-04-13T21:21:00',
    universeName: 'us_preopen_watchlist_v1',
    universeSize: 180,
    preselectedSize: 40,
    evaluatedSize: 32,
    sourceSummary: 'universe=local_us_history; snapshot=optional_us_realtime_quote; history=local_us_first',
    headline: '今日美股盘前优先观察：NVDA NVIDIA',
    universeNotes: ['优先读取本地可用的 US history universe。'],
    scoringNotes: ['流动性、趋势延续、相对强度与 gap context 共同决定排序。'],
    diagnostics: {
      historyStats: {
        localHits: 4,
        networkFetches: 0,
      },
      aiInterpretation: {
        enabled: true,
        status: 'completed',
        topN: 1,
        attemptedCandidates: 1,
        generatedCandidates: 1,
        failedCandidates: 0,
        skippedCandidates: 0,
        modelsUsed: ['gemini/gemini-2.5-flash'],
        fallbackUsed: false,
        message: '已为前 1 名候选生成 AI 解读。',
      },
      scannerData: {
        universeResolution: {
          source: 'local_db_us_history',
          attempts: [
            { fetcher: 'local_us_parquet_dir', status: 'failed', reasonCode: 'local_us_universe_missing' },
            { fetcher: 'local_db_us_history', status: 'success', rows: 4 },
          ],
        },
        snapshotResolution: {
          source: 'optional_us_realtime_quote',
          attempts: [
            { fetcher: 'YfinanceFetcher', status: 'success', rows: 1 },
          ],
        },
        degradedModeUsed: false,
      },
      liveQuoteStats: {
        attemptedCandidates: 1,
        availableCandidates: 1,
        unavailableCandidates: 0,
        sources: ['yfinance'],
      },
    },
    shortlist: [
      {
        ...makeRunDetail().shortlist[0],
        symbol: 'NVDA',
        name: 'NVIDIA',
        reasonSummary: '价格仍站在 MA20/MA60 上方，趋势延续结构尚未破坏。',
        reasons: [
          '价格仍站在 MA20/MA60 上方，趋势延续结构尚未破坏。',
          '20 日与 60 日动量都保持正向，更像可跟踪的趋势延续候选。',
        ],
        keyMetrics: [
          { label: 'Price', value: '964.00' },
          { label: 'Day change', value: '1.7%' },
          { label: '20D avg $vol', value: '$39.5B' },
        ],
        featureSignals: [
          { label: 'Trend', value: '18.4 / 20' },
          { label: 'Momentum', value: '13.2 / 16' },
        ],
        riskNotes: ['Gap risk 偏高，若开盘后不能延续，容易出现快速回吐。'],
        watchContext: [
          { label: 'Pre-open', value: '先看是否仍靠近近 20 日高点，避免强 gap 后立即走弱。' },
          { label: 'Open check', value: '开盘后优先看成交是否延续到日内前 15 分钟。' },
        ],
        boards: [],
        aiInterpretation: {
          available: true,
          status: 'generated',
          summary: 'AI 认为这更像高流动性趋势延续中的 pre-open follow-through setup。',
          opportunityType: 'Trend continuation',
          riskInterpretation: '若 gap 太大但开盘承接不跟，容易演变成冲高回落。',
          watchPlan: '先看 pre-open 稳定性，再看开盘前 15 分钟的成交延续。',
          reviewCommentary: '后续表现仍跑赢基准。',
          provider: 'gemini',
          model: 'gemini/gemini-2.5-flash',
          generatedAt: '2026-04-13T21:20:10',
          message: null,
        },
        realizedOutcome: {
          ...makeRunDetail().shortlist[0].realizedOutcome,
          benchmarkCode: 'SPY',
        },
        diagnostics: {
          historySource: 'local_db',
          benchmarkCode: 'SPY',
          componentScores: { trend: 18.4 },
        },
      },
    ],
  };
}

function makeHkRunDetail(): ScannerRunDetail {
  return {
    ...makeRunDetail(),
    id: 303,
    market: 'hk',
    profile: 'hk_preopen_v1',
    profileLabel: '港股盘前扫描 v1',
    runAt: '2026-04-15T09:10:00',
    completedAt: '2026-04-15T09:11:00',
    universeName: 'hk_preopen_watchlist_v1',
    universeSize: 120,
    preselectedSize: 30,
    evaluatedSize: 18,
    sourceSummary: 'universe=local_db_hk_history+curated_hk_liquid_seed; snapshot=optional_hk_realtime_quote; history=local_hk_first',
    headline: '今日港股开盘优先观察：HK00700 Tencent Holdings',
    universeNotes: ['优先读取本地 HK history universe，并在覆盖不足时补入受控 seed。'],
    scoringNotes: ['流动性、趋势延续、相对强度与开盘 context 共同决定排序。'],
    diagnostics: {
      historyStats: {
        localHits: 4,
        networkFetches: 0,
      },
      aiInterpretation: {
        enabled: true,
        status: 'completed',
        topN: 1,
        attemptedCandidates: 1,
        generatedCandidates: 1,
        failedCandidates: 0,
        skippedCandidates: 0,
        modelsUsed: ['gemini/gemini-2.5-flash'],
        fallbackUsed: false,
        message: '已为前 1 名候选生成 AI 解读。',
      },
      scannerData: {
        universeResolution: {
          source: 'local_db_hk_history+curated_hk_liquid_seed',
          attempts: [
            { fetcher: 'local_db_hk_history', status: 'success', rows: 4 },
            { fetcher: 'curated_hk_liquid_seed', status: 'success', rows: 20 },
          ],
        },
        snapshotResolution: {
          source: 'optional_hk_realtime_quote',
          attempts: [
            { fetcher: 'TwelveDataFetcher', status: 'success', rows: 1 },
          ],
        },
        degradedModeUsed: false,
      },
      liveQuoteStats: {
        attemptedCandidates: 1,
        availableCandidates: 1,
        unavailableCandidates: 0,
        sources: ['twelve_data'],
      },
    },
    shortlist: [
      {
        ...makeRunDetail().shortlist[0],
        symbol: 'HK00700',
        name: 'Tencent Holdings',
        reasonSummary: '价格仍站在 MA20/MA60 上方，趋势延续结构尚未破坏。',
        reasons: [
          '价格仍站在 MA20/MA60 上方，趋势延续结构尚未破坏。',
          '20 日与 60 日动量同步转强，更像可持续跟踪的港股趋势候选。',
        ],
        keyMetrics: [
          { label: '价格', value: '503.50' },
          { label: '日涨跌幅', value: '1.5%' },
          { label: '20日均成交额', value: 'HK$6.2B' },
        ],
        featureSignals: [
          { label: '趋势', value: '18.2 / 20' },
          { label: '动量', value: '12.6 / 16' },
        ],
        riskNotes: ['开盘跳空幅度偏大，若承接不足，容易走成冲高回落。'],
        watchContext: [
          { label: '开盘前', value: '先看是否仍靠近近 20 日高点，避免高开后迅速走弱。' },
          { label: '开盘确认', value: '开盘后优先看前 15 分钟成交是否延续。' },
        ],
        boards: [],
        realizedOutcome: {
          ...makeRunDetail().shortlist[0].realizedOutcome,
          benchmarkCode: 'HK02800',
        },
        diagnostics: {
          historySource: 'local_db',
          benchmarkCode: 'HK02800',
          componentScores: { trend: 18.2 },
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

function makeUsHistoryResponse(): ScannerRunHistoryResponse {
  return {
    total: 1,
    page: 1,
    limit: 6,
    items: [
      {
        ...makeHistoryResponse().items[0],
        id: 202,
        market: 'us',
        profile: 'us_preopen_v1',
        profileLabel: 'US Pre-open Scanner v1',
        runAt: '2026-04-13T21:20:00',
        completedAt: '2026-04-13T21:21:00',
        universeName: 'us_preopen_watchlist_v1',
        universeSize: 180,
        preselectedSize: 40,
        evaluatedSize: 32,
        headline: '今日美股盘前优先观察：NVDA NVIDIA',
        topSymbols: ['NVDA'],
      },
    ],
  };
}

function makePersonalRunsResponse(): ScannerRunHistoryResponse {
  return {
    total: 1,
    page: 1,
    limit: 5,
    items: [
      {
        id: 901,
        market: 'cn',
        profile: 'cn_preopen_v1',
        profileLabel: 'A股盘前扫描 v1',
        status: 'completed',
        runAt: '2026-04-13T08:32:00',
        completedAt: '2026-04-13T08:33:00',
        watchlistDate: '2026-04-13',
        triggerMode: 'manual',
        headline: '我的手动扫描：600001 算力龙头',
        topSymbols: ['600001', '600002'],
        shortlistSize: 2,
        universeName: 'cn_a_liquid_watchlist_v1',
        universeSize: 300,
        preselectedSize: 60,
        evaluatedSize: 48,
        notificationStatus: 'not_attempted',
        failureReason: null,
        changeSummary: {
          available: false,
          previousRunId: null,
          previousWatchlistDate: null,
          newCount: 0,
          retainedCount: 0,
          droppedCount: 0,
          newSymbols: [],
          retainedSymbols: [],
          droppedSymbols: [],
        },
        reviewSummary: {
          available: false,
          reviewWindowDays: 3,
          reviewStatus: 'pending',
          candidateCount: 0,
          reviewedCount: 0,
          pendingCount: 0,
          hitRatePct: null,
          outperformRatePct: null,
          avgSameDayCloseReturnPct: null,
          avgReviewWindowReturnPct: null,
          avgMaxFavorableMovePct: null,
          avgMaxAdverseMovePct: null,
          strongCount: 0,
          mixedCount: 0,
          weakCount: 0,
          bestSymbol: null,
          bestReturnPct: null,
          weakestSymbol: null,
          weakestReturnPct: null,
        },
      },
    ],
  };
}

function makeHkHistoryResponse(): ScannerRunHistoryResponse {
  return {
    total: 1,
    page: 1,
    limit: 6,
    items: [
      {
        ...makeHistoryResponse().items[0],
        id: 303,
        market: 'hk',
        profile: 'hk_preopen_v1',
        profileLabel: '港股盘前扫描 v1',
        runAt: '2026-04-15T09:10:00',
        completedAt: '2026-04-15T09:11:00',
        universeName: 'hk_preopen_watchlist_v1',
        universeSize: 120,
        preselectedSize: 30,
        evaluatedSize: 18,
        headline: '今日港股开盘优先观察：HK00700 Tencent Holdings',
        topSymbols: ['HK00700'],
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

function makeUsStatusResponse(): ScannerOperationalStatus {
  return {
    ...makeStatusResponse(),
    market: 'us',
    profile: 'us_preopen_v1',
    profileLabel: 'US Pre-open Scanner v1',
    scheduleTime: '21:20',
    todayWatchlist: {
      ...makeStatusResponse().todayWatchlist!,
      id: 202,
      headline: '今日美股盘前优先观察：NVDA NVIDIA',
    },
    lastRun: {
      ...makeStatusResponse().lastRun!,
      id: 202,
      headline: '今日美股盘前优先观察：NVDA NVIDIA',
    },
    lastScheduledRun: {
      ...makeStatusResponse().lastScheduledRun!,
      id: 202,
      headline: '今日美股盘前优先观察：NVDA NVIDIA',
    },
    qualitySummary: {
      ...makeStatusResponse().qualitySummary,
      benchmarkCode: 'SPY',
    },
  };
}

function makeHkStatusResponse(): ScannerOperationalStatus {
  return {
    ...makeStatusResponse(),
    market: 'hk',
    profile: 'hk_preopen_v1',
    profileLabel: '港股盘前扫描 v1',
    scheduleTime: '09:10',
    todayWatchlist: {
      ...makeStatusResponse().todayWatchlist!,
      id: 303,
      headline: '今日港股开盘优先观察：HK00700 Tencent Holdings',
    },
    lastRun: {
      ...makeStatusResponse().lastRun!,
      id: 303,
      headline: '今日港股开盘优先观察：HK00700 Tencent Holdings',
    },
    lastScheduledRun: {
      ...makeStatusResponse().lastScheduledRun!,
      id: 303,
      headline: '今日港股开盘优先观察：HK00700 Tencent Holdings',
    },
    qualitySummary: {
      ...makeStatusResponse().qualitySummary,
      benchmarkCode: 'HK02800',
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
    getRuns.mockReset();
    getRun.mockReset();
    getStatus.mockReset();
    runScan.mockReset();
    analyzeAsync.mockReset();

    getRecentWatchlists.mockResolvedValue(makeHistoryResponse());
    getRuns.mockResolvedValue(makePersonalRunsResponse());
    getRun.mockResolvedValue(makeRunDetail());
    getStatus.mockResolvedValue(makeStatusResponse());
    runScan.mockResolvedValue(makeRunDetail());
    analyzeAsync.mockResolvedValue({ taskId: 'task-1' });
  });

  it('renders today watchlist status, recent watchlists, and opens the detail drawer', async () => {
    renderScannerPage();

    expect((await screen.findAllByText('算力龙头')).length).toBeGreaterThan(0);
    expect(screen.getByText('AI算力')).toBeInTheDocument();
    expect(screen.getAllByText('AI 解读').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/临界突破/).length).toBeGreaterThan(0);
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
    expect(screen.getByText('AI 总结')).toBeInTheDocument();
    expect(screen.getByText('诊断信息')).toBeInTheDocument();
  });

  it('renders clear fallback copy when ai interpretation is unavailable', async () => {
    const fallbackRunDetail: ScannerRunDetail = {
      ...makeRunDetail(),
      diagnostics: {
        ...makeRunDetail().diagnostics,
        aiInterpretation: {
          enabled: true,
          status: 'unavailable',
          topN: 1,
          attemptedCandidates: 0,
          generatedCandidates: 0,
          failedCandidates: 0,
          skippedCandidates: 1,
          modelsUsed: [],
          fallbackUsed: false,
          message: 'AI provider 当前不可用，scanner 已自动回退为纯规则型结果。',
        },
      },
      shortlist: [
        {
          ...makeRunDetail().shortlist[0],
          aiInterpretation: {
            available: false,
            status: 'unavailable',
            summary: null,
            opportunityType: null,
            riskInterpretation: null,
            watchPlan: null,
            reviewCommentary: null,
            provider: null,
            model: null,
            generatedAt: null,
            message: 'AI provider 当前不可用，scanner 已自动回退为纯规则型结果。',
          },
        },
      ],
    };
    getRun.mockResolvedValue(fallbackRunDetail);
    runScan.mockResolvedValue(fallbackRunDetail);

    renderScannerPage();

    expect(await screen.findByText('AI provider 当前不可用，scanner 已自动回退为纯规则型结果。')).toBeInTheDocument();
  });

  it('renders bounded run diagnostics for coverage and provider fallback', async () => {
    renderScannerPage();

    expect(await screen.findByText('本次扫描诊断')).toBeInTheDocument();
    expect(screen.getByText('输入池')).toBeInTheDocument();
    expect(screen.getByText('通过流动性/约束')).toBeInTheDocument();
    expect(screen.getByText('进入最终 shortlist')).toBeInTheDocument();
    expect(screen.getByText('多数标的在 profile / liquidity 过滤阶段被淘汰')).toBeInTheDocument();
    expect(screen.getByText(/过滤 260 只/)).toBeInTheDocument();
    expect(screen.getAllByText(/AkshareFetcher/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/EfinanceFetcher/).length).toBeGreaterThan(0);
    expect(screen.getByText('发生 1 次 fallback')).toBeInTheDocument();
  });

  it('keeps personal scanner history visible in admin mode as an additive section', async () => {
    renderScannerPage();

    expect(await screen.findByText('我的近期 runs')).toBeInTheDocument();
    expect(screen.getByText('我的手动扫描：600001 算力龙头')).toBeInTheDocument();
    expect(getRuns).toHaveBeenCalledWith({
      market: 'cn',
      profile: 'cn_preopen_v1',
      page: 1,
      limit: 5,
    });
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

  it('supports switching to the US profile and preserves market-specific defaults', async () => {
    getRecentWatchlists.mockImplementation(async (params?: { market?: string }) => (
      params?.market === 'us' ? makeUsHistoryResponse() : makeHistoryResponse()
    ));
    getStatus.mockImplementation(async (params?: { market?: string }) => (
      params?.market === 'us' ? makeUsStatusResponse() : makeStatusResponse()
    ));
    runScan.mockResolvedValue(makeUsRunDetail());

    renderScannerPage();

    expect((await screen.findAllByText('算力龙头')).length).toBeGreaterThan(0);

    fireEvent.change(screen.getByLabelText('市场'), { target: { value: 'us' } });

    expect(screen.getByText('美股盘前扫描高流动性、相对强度候选，生成 Pre-open Watchlist。')).toBeInTheDocument();

    await waitFor(() => {
      expect(getStatus).toHaveBeenLastCalledWith({
        market: 'us',
        profile: 'us_preopen_v1',
      });
    });

    fireEvent.click(screen.getByRole('button', { name: '运行扫描' }));

    await waitFor(() => {
      expect(runScan).toHaveBeenCalledWith({
        market: 'us',
        profile: 'us_preopen_v1',
        shortlistSize: 5,
        universeLimit: 180,
        detailLimit: 40,
      });
    });

    expect(await screen.findByText('NVDA')).toBeInTheDocument();
    expect(screen.getAllByText('美股').length).toBeGreaterThan(0);
    expect(screen.getByText(/SPY/)).toBeInTheDocument();
  });

  it('supports switching to the HK profile and preserves market-specific defaults', async () => {
    getRecentWatchlists.mockImplementation(async (params?: { market?: string }) => (
      params?.market === 'hk'
        ? makeHkHistoryResponse()
        : params?.market === 'us'
          ? makeUsHistoryResponse()
          : makeHistoryResponse()
    ));
    getStatus.mockImplementation(async (params?: { market?: string }) => (
      params?.market === 'hk'
        ? makeHkStatusResponse()
        : params?.market === 'us'
          ? makeUsStatusResponse()
          : makeStatusResponse()
    ));
    runScan.mockResolvedValue(makeHkRunDetail());

    renderScannerPage();

    expect((await screen.findAllByText('算力龙头')).length).toBeGreaterThan(0);

    fireEvent.change(screen.getByLabelText('市场'), { target: { value: 'hk' } });

    expect(screen.getByText('港股开盘前扫描高流动性、强趋势候选，生成 Opening Watchlist。')).toBeInTheDocument();

    await waitFor(() => {
      expect(getStatus).toHaveBeenLastCalledWith({
        market: 'hk',
        profile: 'hk_preopen_v1',
      });
    });

    fireEvent.click(screen.getByRole('button', { name: '运行扫描' }));

    await waitFor(() => {
      expect(runScan).toHaveBeenCalledWith({
        market: 'hk',
        profile: 'hk_preopen_v1',
        shortlistSize: 5,
        universeLimit: 120,
        detailLimit: 30,
      });
    });

    expect(await screen.findByText('HK00700')).toBeInTheDocument();
    expect(screen.getAllByText('港股').length).toBeGreaterThan(0);
    expect(screen.getByText(/HK02800/)).toBeInTheDocument();
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
