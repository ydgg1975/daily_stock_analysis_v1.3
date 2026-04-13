export interface ScannerRunRequest {
  market?: 'cn' | 'us';
  profile?: string;
  shortlistSize?: number;
  universeLimit?: number;
  detailLimit?: number;
}

export interface ScannerLabeledValue {
  label: string;
  value: string;
}

export interface ScannerNotificationResult {
  attempted: boolean;
  status: string;
  success?: boolean | null;
  channels: string[];
  message?: string | null;
  reportPath?: string | null;
  sentAt?: string | null;
}

export interface ScannerCandidateOutcome {
  reviewStatus: string;
  outcomeLabel: string;
  thesisMatch: string;
  reviewWindowDays: number;
  anchorDate?: string | null;
  windowEndDate?: string | null;
  sameDayCloseReturnPct?: number | null;
  nextDayReturnPct?: number | null;
  reviewWindowReturnPct?: number | null;
  maxFavorableMovePct?: number | null;
  maxAdverseMovePct?: number | null;
  benchmarkCode?: string | null;
  benchmarkReturnPct?: number | null;
  outperformedBenchmark?: boolean | null;
}

export interface ScannerReviewSummary {
  available: boolean;
  reviewWindowDays: number;
  reviewStatus: string;
  candidateCount: number;
  reviewedCount: number;
  pendingCount: number;
  hitRatePct?: number | null;
  outperformRatePct?: number | null;
  avgSameDayCloseReturnPct?: number | null;
  avgReviewWindowReturnPct?: number | null;
  avgMaxFavorableMovePct?: number | null;
  avgMaxAdverseMovePct?: number | null;
  strongCount: number;
  mixedCount: number;
  weakCount: number;
  bestSymbol?: string | null;
  bestReturnPct?: number | null;
  weakestSymbol?: string | null;
  weakestReturnPct?: number | null;
}

export interface ScannerWatchlistDeltaItem {
  symbol: string;
  name?: string | null;
  currentRank?: number | null;
  previousRank?: number | null;
  rankDelta?: number | null;
}

export interface ScannerWatchlistComparison {
  available: boolean;
  previousRunId?: number | null;
  previousWatchlistDate?: string | null;
  newCount: number;
  retainedCount: number;
  droppedCount: number;
  newSymbols: ScannerWatchlistDeltaItem[];
  retainedSymbols: ScannerWatchlistDeltaItem[];
  droppedSymbols: ScannerWatchlistDeltaItem[];
}

export interface ScannerQualitySummary {
  available: boolean;
  reviewWindowDays: number;
  benchmarkCode?: string | null;
  runCount: number;
  reviewedRunCount: number;
  reviewedCandidateCount: number;
  reviewCoveragePct?: number | null;
  avgCandidatesPerRun?: number | null;
  avgShortlistReturnPct?: number | null;
  positiveRunRatePct?: number | null;
  hitRatePct?: number | null;
  outperformRatePct?: number | null;
  positiveCandidateAvgScore?: number | null;
  negativeCandidateAvgScore?: number | null;
}

export interface ScannerCandidate {
  symbol: string;
  name: string;
  rank: number;
  score: number;
  qualityHint?: string | null;
  reasonSummary?: string | null;
  reasons: string[];
  keyMetrics: ScannerLabeledValue[];
  featureSignals: ScannerLabeledValue[];
  riskNotes: string[];
  watchContext: ScannerLabeledValue[];
  boards: string[];
  appearedInRecentRuns: number;
  lastTradeDate?: string | null;
  scanTimestamp?: string | null;
  realizedOutcome: ScannerCandidateOutcome;
  diagnostics: Record<string, unknown>;
}

export interface ScannerRunDetail {
  id: number;
  market: string;
  profile: string;
  profileLabel?: string | null;
  status: string;
  runAt?: string | null;
  completedAt?: string | null;
  watchlistDate?: string | null;
  triggerMode?: string | null;
  universeName: string;
  shortlistSize: number;
  universeSize: number;
  preselectedSize: number;
  evaluatedSize: number;
  sourceSummary?: string | null;
  headline?: string | null;
  universeNotes: string[];
  scoringNotes: string[];
  diagnostics: Record<string, unknown>;
  notification: ScannerNotificationResult;
  failureReason?: string | null;
  comparisonToPrevious: ScannerWatchlistComparison;
  reviewSummary: ScannerReviewSummary;
  shortlist: ScannerCandidate[];
}

export interface ScannerRunHistoryItem {
  id: number;
  market: string;
  profile: string;
  profileLabel?: string | null;
  status: string;
  runAt?: string | null;
  completedAt?: string | null;
  watchlistDate?: string | null;
  triggerMode?: string | null;
  universeName: string;
  shortlistSize: number;
  universeSize: number;
  preselectedSize: number;
  evaluatedSize: number;
  sourceSummary?: string | null;
  headline?: string | null;
  topSymbols: string[];
  notificationStatus?: string | null;
  failureReason?: string | null;
  changeSummary: ScannerWatchlistComparison;
  reviewSummary: ScannerReviewSummary;
}

export interface ScannerRunHistoryResponse {
  total: number;
  page: number;
  limit: number;
  items: ScannerRunHistoryItem[];
}

export interface ScannerOperationalRunSummary {
  id: number;
  watchlistDate?: string | null;
  triggerMode?: string | null;
  status: string;
  runAt?: string | null;
  headline?: string | null;
  shortlistSize: number;
  notificationStatus?: string | null;
  failureReason?: string | null;
}

export interface ScannerOperationalStatus {
  market: string;
  profile: string;
  profileLabel?: string | null;
  watchlistDate: string;
  todayTradingDay: boolean;
  scheduleEnabled: boolean;
  scheduleTime?: string | null;
  scheduleRunImmediately: boolean;
  notificationEnabled: boolean;
  todayWatchlist?: ScannerOperationalRunSummary | null;
  lastRun?: ScannerOperationalRunSummary | null;
  lastScheduledRun?: ScannerOperationalRunSummary | null;
  lastManualRun?: ScannerOperationalRunSummary | null;
  latestFailure?: ScannerOperationalRunSummary | null;
  qualitySummary: ScannerQualitySummary;
}
