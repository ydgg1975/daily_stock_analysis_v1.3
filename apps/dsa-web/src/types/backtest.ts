/**
 * Backtest API type definitions
 * Mirrors api/v1/schemas/backtest.py
 */

// ============ Request / Response ============

export interface BacktestRunRequest {
  code?: string;
  force?: boolean;
  evalWindowDays?: number;
  minAgeDays?: number;
  limit?: number;
}

export interface BacktestRunResponse {
  runId?: number;
  runAt?: string | null;
  processed: number;
  saved: number;
  completed: number;
  insufficient: number;
  errors: number;
  candidateCount?: number;
  noResultReason?: string | null;
  noResultMessage?: string | null;
}

export interface PrepareBacktestSamplesRequest {
  code: string;
  sampleCount?: number;
  evalWindowDays?: number;
  minAgeDays?: number;
  forceRefresh?: boolean;
}

export interface PrepareBacktestSamplesResponse {
  code: string;
  sampleCount: number;
  prepared: number;
  skippedExisting: number;
  marketRowsSaved: number;
  candidateRows: number;
  evalWindowDays: number;
  minAgeDays: number;
  preparedStartDate?: string | null;
  preparedEndDate?: string | null;
  latestPreparedAt?: string | null;
  noResultReason?: string | null;
  noResultMessage?: string | null;
}

export interface BacktestRunHistoryItem {
  id: number;
  code?: string | null;
  evalWindowDays: number;
  minAgeDays: number;
  force: boolean;
  runAt?: string | null;
  completedAt?: string | null;
  processed: number;
  saved: number;
  completed: number;
  insufficient: number;
  errors: number;
  candidateCount: number;
  resultCount: number;
  noResultReason?: string | null;
  noResultMessage?: string | null;
  status: string;
  totalEvaluations: number;
  completedCount: number;
  insufficientCount: number;
  longCount: number;
  cashCount: number;
  winCount: number;
  lossCount: number;
  neutralCount: number;
  winRatePct?: number | null;
  avgStockReturnPct?: number | null;
  avgSimulatedReturnPct?: number | null;
  directionAccuracyPct?: number | null;
  summary?: Record<string, unknown>;
}

export interface BacktestRunHistoryResponse {
  total: number;
  page: number;
  limit: number;
  items: BacktestRunHistoryItem[];
}

export interface BacktestSampleStatusResponse {
  code: string;
  preparedCount: number;
  preparedStartDate?: string | null;
  preparedEndDate?: string | null;
  latestPreparedAt?: string | null;
  evalWindowDays: number;
  minAgeDays: number;
}

export interface BacktestClearResponse {
  code: string;
  deletedRuns: number;
  deletedResults: number;
  deletedSamples: number;
  deletedSummaries: number;
  message?: string | null;
}

// ============ Rule Backtest ============

export interface RuleBacktestParseRequest {
  code: string;
  strategyText: string;
}

export interface RuleBacktestRuleOperand {
  kind: 'indicator' | 'value';
  indicator?: string;
  period?: number | null;
  value?: number | null;
}

export interface RuleBacktestRuleNode {
  type: 'group' | 'comparison';
  op?: 'and' | 'or';
  rules?: RuleBacktestRuleNode[];
  left?: RuleBacktestRuleOperand;
  right?: RuleBacktestRuleOperand;
  compare?: '>' | '<' | '>=' | '<=';
  text?: string;
}

export interface RuleBacktestParseResponse {
  code: string;
  strategyText: string;
  parsedStrategy: {
    version: string;
    timeframe: string;
    sourceText: string;
    normalizedText: string;
    entry: RuleBacktestRuleNode;
    exit: RuleBacktestRuleNode;
    confidence: number;
    needsConfirmation: boolean;
    ambiguities: Array<Record<string, unknown>>;
    summary: Record<string, string>;
    maxLookback: number;
  };
  confidence: number;
  needsConfirmation: boolean;
  ambiguities: Array<Record<string, unknown>>;
  summary: Record<string, string>;
  maxLookback: number;
}

export interface RuleBacktestRunRequest {
  code: string;
  strategyText: string;
  parsedStrategy?: RuleBacktestParseResponse['parsedStrategy'];
  lookbackBars?: number;
  initialCapital?: number;
  feeBps?: number;
  confirmed?: boolean;
}

export interface RuleBacktestTradeItem {
  id?: number;
  runId?: number;
  tradeIndex?: number;
  code: string;
  entryDate?: string | null;
  exitDate?: string | null;
  entryPrice?: number | null;
  exitPrice?: number | null;
  entrySignal?: string | null;
  exitSignal?: string | null;
  returnPct?: number | null;
  holdingDays?: number | null;
  entryRule: RuleBacktestRuleNode;
  exitRule: RuleBacktestRuleNode;
  notes?: string | null;
}

export interface RuleBacktestEquityPointItem {
  date?: string;
  equity?: number;
  cumulativeReturnPct?: number;
  drawdownPct?: number;
}

export interface RuleBacktestRunResponse {
  id: number;
  code: string;
  strategyText: string;
  parsedStrategy: RuleBacktestParseResponse['parsedStrategy'];
  strategyHash: string;
  timeframe: string;
  lookbackBars: number;
  initialCapital: number;
  feeBps: number;
  parsedConfidence?: number | null;
  needsConfirmation: boolean;
  warnings: Array<Record<string, unknown>>;
  runAt?: string | null;
  completedAt?: string | null;
  status: string;
  noResultReason?: string | null;
  noResultMessage?: string | null;
  tradeCount: number;
  winCount: number;
  lossCount: number;
  totalReturnPct?: number | null;
  winRatePct?: number | null;
  avgTradeReturnPct?: number | null;
  maxDrawdownPct?: number | null;
  avgHoldingDays?: number | null;
  finalEquity?: number | null;
  summary: Record<string, unknown>;
  aiSummary?: string | null;
  equityCurve: RuleBacktestEquityPointItem[];
  trades: RuleBacktestTradeItem[];
}

export type RuleBacktestHistoryItem = RuleBacktestRunResponse;

export interface RuleBacktestHistoryResponse {
  total: number;
  page: number;
  limit: number;
  items: RuleBacktestHistoryItem[];
}

// ============ Result Item ============

export interface BacktestResultItem {
  analysisHistoryId: number;
  code: string;
  analysisDate?: string;
  evalWindowDays: number;
  engineVersion: string;
  evalStatus: string;
  evaluatedAt?: string;
  operationAdvice?: string;
  positionRecommendation?: string;
  startPrice?: number;
  endClose?: number;
  maxHigh?: number;
  minLow?: number;
  stockReturnPct?: number;
  directionExpected?: string;
  directionCorrect?: boolean;
  outcome?: string;
  stopLoss?: number;
  takeProfit?: number;
  hitStopLoss?: boolean;
  hitTakeProfit?: boolean;
  firstHit?: string;
  firstHitDate?: string;
  firstHitTradingDays?: number;
  simulatedEntryPrice?: number;
  simulatedExitPrice?: number;
  simulatedExitReason?: string;
  simulatedReturnPct?: number;
}

export interface BacktestResultsResponse {
  total: number;
  page: number;
  limit: number;
  items: BacktestResultItem[];
}

// ============ Performance Metrics ============

export interface PerformanceMetrics {
  scope: string;
  code?: string;
  evalWindowDays: number;
  engineVersion: string;
  computedAt?: string;

  totalEvaluations: number;
  completedCount: number;
  insufficientCount: number;
  longCount: number;
  cashCount: number;
  winCount: number;
  lossCount: number;
  neutralCount: number;

  directionAccuracyPct?: number;
  winRatePct?: number;
  neutralRatePct?: number;
  avgStockReturnPct?: number;
  avgSimulatedReturnPct?: number;

  stopLossTriggerRate?: number;
  takeProfitTriggerRate?: number;
  ambiguousRate?: number;
  avgDaysToFirstHit?: number;

  adviceBreakdown: Record<string, unknown>;
  diagnostics: Record<string, unknown>;
}
