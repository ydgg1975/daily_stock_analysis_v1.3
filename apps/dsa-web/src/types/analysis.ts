/**
 * Analysis-related type definitions.
 * Aligned with the API schema.
 */

// ============ Request Types ============

export interface AnalysisRequest {
  stockCode?: string;
  stockCodes?: string[];
  reportType?: 'simple' | 'detailed' | 'full' | 'brief';
  forceRefresh?: boolean;
  asyncMode?: boolean;
  stockName?: string;
  originalQuery?: string;
  selectionSource?: 'manual' | 'autocomplete' | 'import' | 'image';
}

// ============ Report Types ============

export type ReportLanguage = 'zh' | 'en';

/** Report metadata */
export interface ReportMeta {
  id?: number;  // Analysis history record ID, present for persisted reports
  queryId: string;
  stockCode: string;
  stockName: string;
  reportType: 'simple' | 'detailed' | 'full' | 'brief';
  reportLanguage?: ReportLanguage;
  createdAt: string;
  marketTimestamp?: string;
  marketSessionDate?: string;
  newsPublishedAt?: string;
  reportGeneratedAt?: string;
  currentPrice?: number;
  changePct?: number;
  modelUsed?: string;  // LLM model used for analysis
}

/** Sentiment label */
export type SentimentLabel =
  | '极度悲观'
  | '悲观'
  | '中性'
  | '乐观'
  | '极度乐观'
  | 'Very Bearish'
  | 'Bearish'
  | 'Neutral'
  | 'Bullish'
  | 'Very Bullish';

/** Report summary section */
export interface ReportSummary {
  analysisSummary: string;
  operationAdvice: string;
  trendPrediction: string;
  sentimentScore: number;
  sentimentLabel?: SentimentLabel;
}

/** Strategy section */
export interface ReportStrategy {
  idealBuy?: string;
  secondaryBuy?: string;
  stopLoss?: string;
  takeProfit?: string;
}

export interface StandardReportField {
  label: string;
  value: string;
  source?: string;
  status?: string;
  category?: string;
}

export interface StandardReportTag {
  label: string;
  value: string;
}

export interface StandardReportSummaryPanel {
  stock?: string;
  ticker?: string;
  score?: number;
  currentPrice?: string;
  changeAmount?: string;
  changePct?: string;
  marketTime?: string;
  marketSessionDate?: string;
  sessionLabel?: string;
  operationAdvice?: string;
  trendPrediction?: string;
  oneSentence?: string;
  timeSensitivity?: string;
  tags?: StandardReportTag[];
}

export interface StandardReportRegularMetrics {
  price?: number;
  prevClose?: number;
  changeAmount?: number;
  changePct?: number;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  amplitude?: number;
  volume?: number;
  amount?: number;
  volumeRatio?: number;
  turnoverRate?: number;
  averagePrice?: number;
  vwap?: number;
}

export interface StandardReportMarketBlock {
  regularFields?: StandardReportField[];
  extendedFields?: StandardReportField[];
  consistencyWarnings?: string[];
  regularPriceNumeric?: number;
  regularMetrics?: StandardReportRegularMetrics;
  timeContext?: Record<string, string | undefined>;
}

export interface StandardReportTableSection {
  title: string;
  fields: StandardReportField[];
  note?: string;
}

export interface StandardReportVisualScore {
  value?: number;
  max?: number;
}

export interface StandardReportPricePosition {
  currentPrice?: number;
  ma20?: number;
  ma60?: number;
  distanceToMa20Pct?: number;
  distanceToMa60Pct?: number;
  vsMa20?: string;
  vsMa60?: string;
}

export interface StandardReportRiskOpportunity {
  positiveCount?: number;
  riskCount?: number;
  latestNewsCount?: number;
}

export interface StandardReportTrendStrength {
  value?: number;
  max?: number;
  label?: string;
}

export interface StandardReportVisualBlocks {
  score?: StandardReportVisualScore;
  trendStrength?: StandardReportTrendStrength;
  pricePosition?: StandardReportPricePosition;
  riskOpportunity?: StandardReportRiskOpportunity;
}

export interface StandardReportHighlights {
  positiveCatalysts?: string[];
  riskAlerts?: string[];
  latestNews?: string[];
  newsValueGrade?: string;
  sentimentSummary?: string;
  earningsOutlook?: string;
}

export interface StandardReportBattlePlanItem {
  label: string;
  value: string;
  tone?: string;
}

export interface StandardReportBattlePlanCompact {
  cards?: StandardReportBattlePlanItem[];
  notes?: StandardReportBattlePlanItem[];
  warnings?: string[];
}

export interface StandardReportDecisionContext {
  shortTermView?: string;
  compositeView?: string;
  adjustmentReason?: string;
  changeReason?: string;
  previousScore?: string;
  scoreChange?: string;
  scoreBreakdown?: StandardReportScoreBreakdownItem[];
}

export interface StandardReportScoreBreakdownItem {
  label: string;
  score?: number;
  note?: string;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'history' | string;
}

export interface StandardReportChecklistItem {
  status: 'pass' | 'warn' | 'fail' | 'info' | 'na' | string;
  icon: string;
  text: string;
}

export interface StandardReport {
  title?: Record<string, unknown>;
  summaryPanel?: StandardReportSummaryPanel;
  infoFields?: StandardReportField[];
  positionAdvice?: Record<string, string | undefined>;
  market?: StandardReportMarketBlock;
  technicalFields?: StandardReportField[];
  fundamentalFields?: StandardReportField[];
  earningsFields?: StandardReportField[];
  sentimentFields?: StandardReportField[];
  tableSections?: {
    market?: StandardReportTableSection;
    technical?: StandardReportTableSection;
    fundamental?: StandardReportTableSection;
    earnings?: StandardReportTableSection;
  };
  visualBlocks?: StandardReportVisualBlocks;
  decisionContext?: StandardReportDecisionContext;
  highlights?: StandardReportHighlights;
  battleFields?: StandardReportField[];
  battlePlanCompact?: StandardReportBattlePlanCompact;
  battleWarnings?: string[];
  checklist?: string[];
  checklistItems?: StandardReportChecklistItem[];
}

/** Details section */
export interface ReportDetails {
  newsContent?: string;
  rawResult?: Record<string, unknown>;
  contextSnapshot?: Record<string, unknown>;
  standardReport?: StandardReport;
  financialReport?: Record<string, unknown>;
  dividendMetrics?: Record<string, unknown>;
}

/** Full analysis report */
export interface AnalysisReport {
  meta: ReportMeta;
  summary: ReportSummary;
  strategy?: ReportStrategy;
  details?: ReportDetails;
}

// ============ Analysis Result Types ============

/** Sync analysis response */
export interface AnalysisResult {
  queryId: string;
  stockCode: string;
  stockName: string;
  report: AnalysisReport;
  createdAt: string;
}

/** Async task accepted response */
export interface TaskAccepted {
  taskId: string;
  status: 'pending' | 'processing';
  message?: string;
}

export interface BatchTaskAcceptedItem {
  taskId: string;
  stockCode: string;
  status: 'pending' | 'processing';
  message?: string;
}

export interface BatchDuplicateTaskItem {
  stockCode: string;
  existingTaskId: string;
  message: string;
}

export interface BatchTaskAcceptedResponse {
  accepted: BatchTaskAcceptedItem[];
  duplicates: BatchDuplicateTaskItem[];
  message: string;
}

export type AnalyzeAsyncResponse = TaskAccepted | BatchTaskAcceptedResponse;

export type AnalyzeResponse = AnalysisResult | AnalyzeAsyncResponse;

/** Task status */
export interface TaskStatus {
  taskId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress?: number;
  result?: AnalysisResult;
  error?: string;
  stockName?: string;
  originalQuery?: string;
  selectionSource?: string;
}

/** Task details used by task list and SSE events */
export interface TaskInfo {
  taskId: string;
  stockCode: string;
  stockName?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  message?: string;
  reportType: string;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  error?: string;
  originalQuery?: string;
  selectionSource?: string;
}

/** Task list response */
export interface TaskListResponse {
  total: number;
  pending: number;
  processing: number;
  tasks: TaskInfo[];
}

/** Duplicate task error response */
export interface DuplicateTaskError {
  error: 'duplicate_task';
  message: string;
  stockCode: string;
  existingTaskId: string;
}

// ============ History Types ============

/** History item summary */
export interface HistoryItem {
  id: number;  // Record primary key ID, always present for persisted history items
  queryId: string;  // Linked analysis query ID
  stockCode: string;
  stockName?: string;
  reportType?: string;
  sentimentScore?: number;
  operationAdvice?: string;
  createdAt: string;
}

/** History list response */
export interface HistoryListResponse {
  total: number;
  page: number;
  limit: number;
  items: HistoryItem[];
}

/** News item */
export interface NewsIntelItem {
  title: string;
  snippet: string;
  url: string;
}

/** News response */
export interface NewsIntelResponse {
  total: number;
  items: NewsIntelItem[];
}

/** History filter parameters */
export interface HistoryFilters {
  stockCode?: string;
  startDate?: string;
  endDate?: string;
}

/** History pagination parameters */
export interface HistoryPagination {
  page: number;
  limit: number;
}

// ============ Error Types ============

export interface ApiError {
  error: string;
  message: string;
  detail?: Record<string, unknown>;
}

// ============ Helper Functions ============

/** Get sentiment label by score */
export const getSentimentLabel = (score: number, language: ReportLanguage = 'zh'): SentimentLabel => {
  if (language === 'en') {
    if (score <= 20) return 'Very Bearish';
    if (score <= 40) return 'Bearish';
    if (score <= 60) return 'Neutral';
    if (score <= 80) return 'Bullish';
    return 'Very Bullish';
  }
  if (score <= 20) return '极度悲观';
  if (score <= 40) return '悲观';
  if (score <= 60) return '中性';
  if (score <= 80) return '乐观';
  return '极度乐观';
};

/** Get sentiment color by score */
export const getSentimentColor = (score: number): string => {
  if (score <= 20) return '#ef4444'; // red-500
  if (score <= 40) return '#f97316'; // orange-500
  if (score <= 60) return '#eab308'; // yellow-500
  if (score <= 80) return '#22c55e'; // green-500
  return '#10b981'; // emerald-500
};
