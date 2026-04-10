/**
 * Backtest API type definitions
 * Mirrors api/v1/schemas/backtest.py
 */

export type AssumptionMap = Record<string, unknown>;

export interface StatusHistoryItem {
  status: string;
  at?: string;
}

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
  candidateCount: number;
  noResultReason?: string | null;
  noResultMessage?: string | null;
  latestPreparedSampleDate?: string | null;
  latestEligibleSampleDate?: string | null;
  excludedRecentReason?: string | null;
  excludedRecentMessage?: string | null;
  evaluationMode?: string | null;
  requestedMode?: string | null;
  resolvedSource?: string | null;
  fallbackUsed?: boolean | null;
  pricingResolvedSource?: string | null;
  pricingFallbackUsed?: boolean | null;
  evaluationWindowTradingBars?: number | null;
  maturityCalendarDays?: number | null;
  executionAssumptions: AssumptionMap;
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
  latestPreparedSampleDate?: string | null;
  latestEligibleSampleDate?: string | null;
  excludedRecentReason?: string | null;
  excludedRecentMessage?: string | null;
  noResultReason?: string | null;
  noResultMessage?: string | null;
  requestedMode?: string | null;
  resolvedSource?: string | null;
  fallbackUsed?: boolean | null;
  pricingResolvedSource?: string | null;
  pricingFallbackUsed?: boolean | null;
  evaluationWindowTradingBars?: number | null;
  maturityCalendarDays?: number | null;
}

export interface BacktestRunHistoryItem {
  id: number;
  code?: string | null;
  evalWindowDays: number;
  evaluationWindowTradingBars?: number | null;
  minAgeDays: number;
  maturityCalendarDays?: number | null;
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
  summary: Record<string, unknown>;
  evaluationMode?: string | null;
  requestedMode?: string | null;
  resolvedSource?: string | null;
  fallbackUsed?: boolean | null;
  executionAssumptions: AssumptionMap;
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
  latestPreparedSampleDate?: string | null;
  latestEligibleSampleDate?: string | null;
  excludedRecentReason?: string | null;
  excludedRecentMessage?: string | null;
  evalWindowDays: number;
  minAgeDays: number;
  requestedMode?: string | null;
  resolvedSource?: string | null;
  fallbackUsed?: boolean | null;
  pricingResolvedSource?: string | null;
  pricingFallbackUsed?: boolean | null;
  evaluationWindowTradingBars?: number | null;
  maturityCalendarDays?: number | null;
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
  code?: string;
  strategyText: string;
  startDate?: string;
  endDate?: string;
  initialCapital?: number;
  feeBps?: number;
  slippageBps?: number;
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

export interface RuleBacktestParsedStrategy {
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
  strategyKind?: string;
  setup?: Record<string, unknown>;
  strategySpec?: Record<string, unknown>;
  executable?: boolean;
  normalizationState?: string;
  assumptions?: Array<Record<string, unknown>>;
  assumptionGroups?: Array<Record<string, unknown>>;
  detectedStrategyFamily?: string | null;
  unsupportedReason?: string | null;
  unsupportedDetails?: Array<Record<string, unknown>>;
  unsupportedExtensions?: Array<Record<string, unknown>>;
  coreIntentSummary?: string | null;
  interpretationConfidence?: number | null;
  supportedPortionSummary?: string | null;
  rewriteSuggestions?: Array<Record<string, unknown>>;
  parseWarnings?: Array<Record<string, unknown>>;
}

export interface RuleBacktestParseResponse {
  code?: string;
  strategyText: string;
  parsedStrategy: RuleBacktestParsedStrategy;
  normalizedStrategyFamily?: string;
  detectedStrategyFamily?: string | null;
  executable?: boolean;
  normalizationState?: string;
  assumptions?: Array<Record<string, unknown>>;
  assumptionGroups?: Array<Record<string, unknown>>;
  unsupportedReason?: string | null;
  unsupportedDetails?: Array<Record<string, unknown>>;
  unsupportedExtensions?: Array<Record<string, unknown>>;
  coreIntentSummary?: string | null;
  interpretationConfidence?: number | null;
  supportedPortionSummary?: string | null;
  rewriteSuggestions?: Array<Record<string, unknown>>;
  parseWarnings?: Array<Record<string, unknown>>;
  confidence: number;
  needsConfirmation: boolean;
  ambiguities: Array<Record<string, unknown>>;
  summary: Record<string, string>;
  maxLookback: number;
}

export interface RuleBacktestRunRequest {
  code: string;
  strategyText: string;
  parsedStrategy?: RuleBacktestParsedStrategy;
  startDate?: string;
  endDate?: string;
  lookbackBars?: number;
  initialCapital?: number;
  feeBps?: number;
  slippageBps?: number;
  benchmarkMode?: string;
  benchmarkCode?: string;
  confirmed?: boolean;
  waitForCompletion?: boolean;
}

export interface RuleBacktestTradeItem {
  id?: number;
  runId?: number;
  tradeIndex?: number;
  code: string;
  entrySignalDate?: string | null;
  exitSignalDate?: string | null;
  entryDate?: string | null;
  exitDate?: string | null;
  entryPrice?: number | null;
  exitPrice?: number | null;
  entrySignal?: string | null;
  exitSignal?: string | null;
  entryTrigger?: string | null;
  exitTrigger?: string | null;
  returnPct?: number | null;
  holdingDays?: number | null;
  holdingBars?: number | null;
  holdingCalendarDays?: number | null;
  entryRule: RuleBacktestRuleNode | Record<string, unknown>;
  exitRule: RuleBacktestRuleNode | Record<string, unknown>;
  entryIndicators: Record<string, unknown>;
  exitIndicators: Record<string, unknown>;
  entryFillBasis?: string | null;
  exitFillBasis?: string | null;
  signalPriceBasis?: string | null;
  priceBasis?: string | null;
  feeBps?: number | null;
  slippageBps?: number | null;
  entryFeeAmount?: number | null;
  exitFeeAmount?: number | null;
  entrySlippageAmount?: number | null;
  exitSlippageAmount?: number | null;
  notes?: string | null;
}

export interface RuleBacktestEquityPointItem {
  date?: string;
  equity?: number;
  cumulativeReturnPct?: number;
  drawdownPct?: number;
  close?: number | null;
  signalSummary?: string | null;
  targetPosition?: number | null;
  executedAction?: string | null;
  fillPrice?: number | null;
  sharesHeld?: number | null;
  cash?: number | null;
  holdingsValue?: number | null;
  totalPortfolioValue?: number | null;
  positionState?: string | null;
  exposurePct?: number | null;
  feeAmount?: number | null;
  slippageAmount?: number | null;
  notes?: string | null;
}

export interface RuleBacktestBenchmarkPointItem {
  date?: string;
  close?: number;
  normalizedValue?: number;
  cumulativeReturnPct?: number;
}

export interface RuleBacktestBenchmarkSummary {
  label?: string;
  code?: string | null;
  method?: string;
  requestedMode?: string | null;
  resolvedMode?: string | null;
  normalizedBase?: number;
  priceBasis?: string;
  startDate?: string | null;
  endDate?: string | null;
  startPrice?: number | null;
  endPrice?: number | null;
  returnPct?: number | null;
  unavailableReason?: string | null;
  autoResolved?: boolean;
  fallbackUsed?: boolean;
}

export interface RuleBacktestDailyReturnPointItem {
  date?: string;
  equity?: number;
  dailyReturnPct?: number;
  dailyPnl?: number;
}

export interface RuleBacktestExposurePointItem {
  date?: string;
  exposure?: number;
  positionState?: string;
  executedAction?: string | null;
  fillPrice?: number | null;
}

export interface RuleBacktestAuditRowItem {
  date?: string;
  symbolClose?: number | null;
  benchmarkClose?: number | null;
  position?: number | null;
  shares?: number | null;
  dailyReturn?: number | null;
  cumulativeReturn?: number | null;
  benchmarkCumulativeReturn?: number | null;
  buyHoldCumulativeReturn?: number | null;
  action?: string | null;
  signalSummary?: string | null;
  drawdownPct?: number | null;
  positionState?: string | null;
  fees?: number | null;
  slippage?: number | null;
  notes?: string | null;
  unavailableReason?: string | null;
  targetPosition?: number | null;
  executedAction?: string | null;
  fillPrice?: number | null;
  sharesHeld?: number | null;
  cash?: number | null;
  holdingsValue?: number | null;
  totalPortfolioValue?: number | null;
  exposurePct?: number | null;
  dailyPnl?: number | null;
  dailyReturnPct?: number | null;
  cumulativeStrategyReturnPct?: number | null;
  cumulativeBenchmarkReturnPct?: number | null;
  cumulativeBuyAndHoldReturnPct?: number | null;
}

export interface RuleBacktestRunResponse {
  id: number;
  code: string;
  strategyText: string;
  parsedStrategy: RuleBacktestParsedStrategy;
  strategyHash: string;
  timeframe: string;
  startDate?: string | null;
  endDate?: string | null;
  periodStart?: string | null;
  periodEnd?: string | null;
  lookbackBars: number;
  initialCapital: number;
  feeBps: number;
  slippageBps: number;
  parsedConfidence?: number | null;
  needsConfirmation: boolean;
  warnings: Array<Record<string, unknown>>;
  runAt?: string | null;
  completedAt?: string | null;
  status: string;
  statusMessage?: string | null;
  statusHistory: StatusHistoryItem[];
  noResultReason?: string | null;
  noResultMessage?: string | null;
  tradeCount: number;
  winCount: number;
  lossCount: number;
  totalReturnPct?: number | null;
  annualizedReturnPct?: number | null;
  benchmarkMode?: string | null;
  benchmarkCode?: string | null;
  benchmarkReturnPct?: number | null;
  excessReturnVsBenchmarkPct?: number | null;
  buyAndHoldReturnPct?: number | null;
  excessReturnVsBuyAndHoldPct?: number | null;
  winRatePct?: number | null;
  avgTradeReturnPct?: number | null;
  maxDrawdownPct?: number | null;
  avgHoldingDays?: number | null;
  avgHoldingBars?: number | null;
  avgHoldingCalendarDays?: number | null;
  finalEquity?: number | null;
  summary: Record<string, unknown>;
  executionAssumptions: AssumptionMap;
  benchmarkCurve: RuleBacktestBenchmarkPointItem[];
  benchmarkSummary: RuleBacktestBenchmarkSummary;
  buyAndHoldCurve?: RuleBacktestBenchmarkPointItem[];
  buyAndHoldSummary?: RuleBacktestBenchmarkSummary;
  auditRows?: RuleBacktestAuditRowItem[];
  dailyReturnSeries: RuleBacktestDailyReturnPointItem[];
  exposureCurve: RuleBacktestExposurePointItem[];
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
  analysisDate?: string | null;
  evalWindowDays: number;
  evaluationWindowTradingBars?: number | null;
  engineVersion: string;
  evalStatus: string;
  evaluatedAt?: string | null;
  operationAdvice?: string | null;
  positionRecommendation?: string | null;
  startPrice?: number | null;
  endClose?: number | null;
  maxHigh?: number | null;
  minLow?: number | null;
  stockReturnPct?: number | null;
  directionExpected?: string | null;
  directionCorrect?: boolean | null;
  outcome?: string | null;
  stopLoss?: number | null;
  takeProfit?: number | null;
  hitStopLoss?: boolean | null;
  hitTakeProfit?: boolean | null;
  firstHit?: string | null;
  firstHitDate?: string | null;
  firstHitTradingDays?: number | null;
  simulatedEntryPrice?: number | null;
  simulatedExitPrice?: number | null;
  simulatedExitReason?: string | null;
  simulatedReturnPct?: number | null;
  marketDataSources: string[];
  executionAssumptions: AssumptionMap;
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
  code?: string | null;
  evalWindowDays: number;
  evaluationWindowTradingBars?: number | null;
  engineVersion: string;
  computedAt?: string | null;
  totalEvaluations: number;
  completedCount: number;
  insufficientCount: number;
  longCount: number;
  cashCount: number;
  winCount: number;
  lossCount: number;
  neutralCount: number;
  directionAccuracyPct?: number | null;
  winRatePct?: number | null;
  neutralRatePct?: number | null;
  avgStockReturnPct?: number | null;
  avgSimulatedReturnPct?: number | null;
  stopLossTriggerRate?: number | null;
  takeProfitTriggerRate?: number | null;
  ambiguousRate?: number | null;
  avgDaysToFirstHit?: number | null;
  adviceBreakdown: Record<string, unknown>;
  diagnostics: Record<string, unknown>;
  evaluationMode?: string | null;
  requestedMode?: string | null;
  resolvedSource?: string | null;
  fallbackUsed?: boolean | null;
  executionAssumptions: AssumptionMap;
}
