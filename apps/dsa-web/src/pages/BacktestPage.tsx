import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useLocation, useNavigate } from 'react-router-dom';
import { backtestApi } from '../api/backtest';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { WorkspacePageHeader } from '../components/common';
import DeterministicBacktestFlow, {
  type RuleWizardStep,
} from '../components/backtest/DeterministicBacktestFlow';
import HistoricalEvaluationPanel from '../components/backtest/HistoricalEvaluationPanel';
import {
  getDefaultRuleDateRange,
  getBenchmarkModeLabel,
  getPeriodicNumber,
  getPeriodicString,
  type RuleBenchmarkMode,
  getStrategyPreviewSpec,
  parsePositiveInt,
} from '../components/backtest/shared';
import type {
  AssumptionMap,
  BacktestResultItem,
  BacktestRunHistoryItem,
  BacktestRunResponse,
  BacktestSampleStatusResponse,
  PerformanceMetrics,
  PrepareBacktestSamplesResponse,
  RuleBacktestHistoryItem,
  RuleBacktestParseResponse,
  RuleBacktestRunResponse,
} from '../types/backtest';

const HISTORICAL_PAGE_SIZE = 20;
const HISTORY_PAGE_SIZE = 10;
const RULE_HISTORY_PAGE_SIZE = 10;

type ActiveModule = 'historical' | 'rule';
type ControlPanelMode = 'normal' | 'professional';
type BacktestPageLocationState = {
  draftRun?: RuleBacktestRunResponse;
  prefillCode?: string;
  prefillName?: string;
};

type PerformanceNotice = {
  tone: 'warning' | 'danger';
  message: string;
};

function buildRuleParseSignature(payload: {
  code: string;
  strategyText: string;
  startDate: string;
  endDate: string;
  initialCapital: string;
  feeBps: string;
  slippageBps: string;
}): string {
  return JSON.stringify({
    code: payload.code.trim().toUpperCase(),
    strategyText: payload.strategyText.trim(),
    startDate: payload.startDate,
    endDate: payload.endDate,
    initialCapital: payload.initialCapital.trim(),
    feeBps: payload.feeBps.trim(),
    slippageBps: payload.slippageBps.trim(),
  });
}

const WORKBENCH_PANEL_TRANSITION = {
  duration: 0.26,
  ease: [0.22, 1, 0.36, 1] as const,
};

const BacktestPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    document.title = '回测 - WolfyStock';
  }, []);

  const [activeModule, setActiveModule] = useState<ActiveModule>('rule');
  const [controlPanelMode, setControlPanelMode] = useState<ControlPanelMode>('normal');
  const [codeFilter, setCodeFilter] = useState('');
  const [evaluationBars, setEvaluationBars] = useState('10');
  const [maturityDays, setMaturityDays] = useState('14');
  const [samplePreset, setSamplePreset] = useState('60');
  const [customSampleCount, setCustomSampleCount] = useState('252');
  const [forceReplaceResults, setForceReplaceResults] = useState(false);

  const [isRunningHistoricalEval, setIsRunningHistoricalEval] = useState(false);
  const [runResult, setRunResult] = useState<BacktestRunResponse | null>(null);
  const [runError, setRunError] = useState<ParsedApiError | null>(null);

  const [prepareResult, setPrepareResult] = useState<PrepareBacktestSamplesResponse | null>(null);
  const [prepareError, setPrepareError] = useState<ParsedApiError | null>(null);
  const [isPreparingSamples, setIsPreparingSamples] = useState(false);

  const [pageError, setPageError] = useState<ParsedApiError | null>(null);
  const [historyError, setHistoryError] = useState<ParsedApiError | null>(null);
  const [sampleStatusError, setSampleStatusError] = useState<ParsedApiError | null>(null);

  const [sampleStatus, setSampleStatus] = useState<BacktestSampleStatusResponse | null>(null);
  const [results, setResults] = useState<BacktestResultItem[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [isLoadingResults, setIsLoadingResults] = useState(false);

  const [historyItems, setHistoryItems] = useState<BacktestRunHistoryItem[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingSampleStatus, setIsLoadingSampleStatus] = useState(false);

  const [overallPerf, setOverallPerf] = useState<PerformanceMetrics | null>(null);
  const [stockPerf, setStockPerf] = useState<PerformanceMetrics | null>(null);
  const [isLoadingPerf, setIsLoadingPerf] = useState(false);
  const [performanceNotice, setPerformanceNotice] = useState<PerformanceNotice | null>(null);

  const [ruleStrategyText, setRuleStrategyText] = useState(
    '资金100000，从2025-01-01到2025-12-31，每天买100股ORCL，买到资金耗尽为止',
  );
  const [ruleStartDate, setRuleStartDate] = useState(() => getDefaultRuleDateRange().startDate);
  const [ruleEndDate, setRuleEndDate] = useState(() => getDefaultRuleDateRange().endDate);
  const [ruleLookbackBars, setRuleLookbackBars] = useState('252');
  const [ruleInitialCapital, setRuleInitialCapital] = useState('100000');
  const [ruleFeeBps, setRuleFeeBps] = useState('0');
  const [ruleSlippageBps, setRuleSlippageBps] = useState('0');
  const [ruleBenchmarkMode, setRuleBenchmarkMode] = useState<RuleBenchmarkMode>('auto');
  const [ruleBenchmarkCode, setRuleBenchmarkCode] = useState('');
  const [ruleParsedStrategy, setRuleParsedStrategy] = useState<RuleBacktestParseResponse | null>(null);
  const [ruleConfirmed, setRuleConfirmed] = useState(false);
  const [isParsingRuleStrategy, setIsParsingRuleStrategy] = useState(false);
  const [ruleParseError, setRuleParseError] = useState<ParsedApiError | null>(null);
  const [isSubmittingRuleBacktest, setIsSubmittingRuleBacktest] = useState(false);
  const [ruleRunError, setRuleRunError] = useState<ParsedApiError | null>(null);
  const [ruleHistoryItems, setRuleHistoryItems] = useState<RuleBacktestHistoryItem[]>([]);
  const [ruleHistoryTotal, setRuleHistoryTotal] = useState(0);
  const [ruleHistoryPage, setRuleHistoryPage] = useState(1);
  const [isLoadingRuleHistory, setIsLoadingRuleHistory] = useState(false);
  const [ruleHistoryError, setRuleHistoryError] = useState<ParsedApiError | null>(null);
  const [selectedRuleRunId, setSelectedRuleRunId] = useState<number | null>(null);
  const [ruleCurrentStep, setRuleCurrentStep] = useState<RuleWizardStep>('symbol');
  const [ruleParseSignature, setRuleParseSignature] = useState<string | null>(null);
  const [appliedRewriteText, setAppliedRewriteText] = useState<string | null>(null);

  const normalizedCode = codeFilter.trim().toUpperCase();
  const resolvedSampleCount = samplePreset === 'custom'
    ? parsePositiveInt(customSampleCount, 252)
    : parsePositiveInt(samplePreset, 60);

  const currentRuleParseSignature = useMemo(() => buildRuleParseSignature({
    code: normalizedCode,
    strategyText: ruleStrategyText,
    startDate: ruleStartDate,
    endDate: ruleEndDate,
    initialCapital: ruleInitialCapital,
    feeBps: ruleFeeBps,
    slippageBps: ruleSlippageBps,
  }), [normalizedCode, ruleEndDate, ruleFeeBps, ruleInitialCapital, ruleSlippageBps, ruleStartDate, ruleStrategyText]);

  const isRuleParseStale = Boolean(ruleParsedStrategy && ruleParseSignature && ruleParseSignature !== currentRuleParseSignature);

  const historicalAssumptions = runResult?.executionAssumptions
    || overallPerf?.executionAssumptions
    || results[0]?.executionAssumptions
    || null;

  const historicalPerfSnapshot = stockPerf || overallPerf;
  const selectedHistoricalRun = useMemo(
    () => historyItems.find((item) => item.id === selectedRunId) || null,
    [historyItems, selectedRunId],
  );

  const historicalSourceMetadata = useMemo(() => {
    const candidates = [
      runResult,
      selectedHistoricalRun,
      sampleStatus,
      stockPerf,
      overallPerf,
      prepareResult,
    ];

    const firstString = (selector: (candidate: typeof candidates[number]) => string | null | undefined) => {
      for (const candidate of candidates) {
        const value = selector(candidate);
        if (typeof value === 'string' && value.trim()) return value;
      }
      return null;
    };

    const firstBoolean = (selector: (candidate: typeof candidates[number]) => boolean | null | undefined) => {
      for (const candidate of candidates) {
        const value = selector(candidate);
        if (typeof value === 'boolean') return value;
      }
      return null;
    };

    return {
      requestedMode: firstString((candidate) => candidate?.requestedMode),
      resolvedSource: firstString((candidate) => candidate?.resolvedSource),
      fallbackUsed: firstBoolean((candidate) => candidate?.fallbackUsed),
    };
  }, [overallPerf, prepareResult, runResult, sampleStatus, selectedHistoricalRun, stockPerf]);

  const historicalSummaryItems = useMemo(() => ([
    {
      label: '已准备样本',
      value: sampleStatus?.preparedCount != null ? String(sampleStatus.preparedCount) : '--',
      note: sampleStatus?.preparedStartDate && sampleStatus?.preparedEndDate
        ? `${sampleStatus.preparedStartDate} -> ${sampleStatus.preparedEndDate}`
        : '历史分析样本',
    },
    {
      label: '有效评估',
      value: historicalPerfSnapshot?.completedCount != null ? String(historicalPerfSnapshot.completedCount) : '--',
      note: historicalPerfSnapshot?.totalEvaluations != null
        ? `总样本 ${historicalPerfSnapshot.totalEvaluations}`
        : '完成并纳入统计的样本数',
    },
    {
      label: '方向准确率',
      value: historicalPerfSnapshot?.directionAccuracyPct != null ? `${historicalPerfSnapshot.directionAccuracyPct.toFixed(2)}%` : '--',
      note: '信号方向与后续走势是否一致',
    },
    {
      label: '胜率',
      value: historicalPerfSnapshot?.winRatePct != null ? `${historicalPerfSnapshot.winRatePct.toFixed(2)}%` : '--',
      note: '未来窗口最终是否为正收益',
    },
    {
      label: '平均远期收益',
      value: historicalPerfSnapshot?.avgSimulatedReturnPct != null ? `${historicalPerfSnapshot.avgSimulatedReturnPct.toFixed(2)}%` : '--',
      note: '样本级未来窗口收益',
    },
    {
      label: '平均标的收益',
      value: historicalPerfSnapshot?.avgStockReturnPct != null ? `${historicalPerfSnapshot.avgStockReturnPct.toFixed(2)}%` : '--',
      note: '同一窗口内标的原始涨跌幅',
    },
  ]), [
    historicalPerfSnapshot?.completedCount,
    historicalPerfSnapshot?.directionAccuracyPct,
    historicalPerfSnapshot?.avgSimulatedReturnPct,
    historicalPerfSnapshot?.avgStockReturnPct,
    historicalPerfSnapshot?.totalEvaluations,
    historicalPerfSnapshot?.winRatePct,
    sampleStatus?.preparedCount,
    sampleStatus?.preparedEndDate,
    sampleStatus?.preparedStartDate,
  ]);

  const historicalSampleTransparency = useMemo(() => {
    const latestPreparedSampleDate = runResult?.latestPreparedSampleDate
      || sampleStatus?.latestPreparedSampleDate
      || prepareResult?.latestPreparedSampleDate
      || null;
    const latestEligibleSampleDate = runResult?.latestEligibleSampleDate
      || sampleStatus?.latestEligibleSampleDate
      || prepareResult?.latestEligibleSampleDate
      || null;
    const excludedRecentMessage = runResult?.excludedRecentMessage
      || sampleStatus?.excludedRecentMessage
      || prepareResult?.excludedRecentMessage
      || null;
    const pricingResolvedSource = runResult?.pricingResolvedSource
      || sampleStatus?.pricingResolvedSource
      || prepareResult?.pricingResolvedSource
      || historicalSourceMetadata.resolvedSource
      || null;
    const pricingFallbackUsed = runResult?.pricingFallbackUsed
      ?? sampleStatus?.pricingFallbackUsed
      ?? prepareResult?.pricingFallbackUsed
      ?? historicalSourceMetadata.fallbackUsed
      ?? null;

    const parts = [
      `最新已准备样本: ${latestPreparedSampleDate || '--'}`,
      `最新可评估样本: ${latestEligibleSampleDate || '--'}`,
    ];
    if (excludedRecentMessage) parts.push(`较新日期未纳入原因: ${excludedRecentMessage}`);
    if (pricingResolvedSource) {
      parts.push(`实际定价来源: ${pricingResolvedSource}${pricingFallbackUsed == null ? '' : `（${pricingFallbackUsed ? '发生回退' : '未回退'}）`}`);
    }
    return parts.join(' · ');
  }, [
    historicalSourceMetadata.fallbackUsed,
    historicalSourceMetadata.resolvedSource,
    prepareResult?.excludedRecentMessage,
    prepareResult?.latestEligibleSampleDate,
    prepareResult?.latestPreparedSampleDate,
    prepareResult?.pricingFallbackUsed,
    prepareResult?.pricingResolvedSource,
    runResult?.excludedRecentMessage,
    runResult?.latestEligibleSampleDate,
    runResult?.latestPreparedSampleDate,
    runResult?.pricingFallbackUsed,
    runResult?.pricingResolvedSource,
    sampleStatus?.excludedRecentMessage,
    sampleStatus?.latestEligibleSampleDate,
    sampleStatus?.latestPreparedSampleDate,
    sampleStatus?.pricingFallbackUsed,
    sampleStatus?.pricingResolvedSource,
  ]);

  const previewRuleAssumptions = useMemo<AssumptionMap>(() => ({
    timeframe: ruleParsedStrategy?.parsedStrategy.timeframe || 'daily',
    price_basis: 'close',
    signal_evaluation_timing: 'bar close',
    entry_fill_timing: 'next bar open',
    exit_fill_timing: 'next bar open; final bar may force close at close',
    position_sizing: '100% capital when long, otherwise cash',
    fee_bps_per_side: Number.parseFloat(ruleFeeBps) || 0,
    slippage_bps_per_side: Number.parseFloat(ruleSlippageBps) || 0,
  }), [ruleFeeBps, ruleParsedStrategy?.parsedStrategy.timeframe, ruleSlippageBps]);

  const applyRuleRunDraft = useCallback((data: RuleBacktestRunResponse) => {
    const parsedStrategyPayload = data.parsedStrategy as unknown as Record<string, unknown>;
    const detectedStrategyFamily = data.parsedStrategy.detectedStrategyFamily
      ?? (typeof parsedStrategyPayload.detected_strategy_family === 'string' ? parsedStrategyPayload.detected_strategy_family : undefined);
    const unsupportedExtensions = data.parsedStrategy.unsupportedExtensions
      ?? (Array.isArray(parsedStrategyPayload.unsupported_extensions) ? parsedStrategyPayload.unsupported_extensions as Array<Record<string, unknown>> : undefined);
    const coreIntentSummary = data.parsedStrategy.coreIntentSummary
      ?? (typeof parsedStrategyPayload.core_intent_summary === 'string' ? parsedStrategyPayload.core_intent_summary : undefined);
    const interpretationConfidence = data.parsedStrategy.interpretationConfidence
      ?? (typeof parsedStrategyPayload.interpretation_confidence === 'number' ? parsedStrategyPayload.interpretation_confidence : undefined);
    setSelectedRuleRunId(data.id);
    setActiveModule('rule');
    setCodeFilter(data.code);
    setRuleStrategyText(data.strategyText);
    setRuleStartDate(data.startDate || '');
    setRuleEndDate(data.endDate || '');
    setRuleLookbackBars(String(data.lookbackBars || 252));
    setRuleInitialCapital(String(data.initialCapital || 100000));
    setRuleFeeBps(String(data.feeBps ?? 0));
    setRuleSlippageBps(String(data.slippageBps ?? 0));
    setRuleBenchmarkMode((data.benchmarkMode as RuleBenchmarkMode | undefined) || 'auto');
    setRuleBenchmarkCode(data.benchmarkCode || '');
    const parsedStrategySummary = (data.summary.parsedStrategySummary as Record<string, string> | undefined)
      || data.parsedStrategy.summary;
    setRuleParsedStrategy({
      code: data.code,
      strategyText: data.strategyText,
      parsedStrategy: {
        ...data.parsedStrategy,
        summary: parsedStrategySummary,
      },
      normalizedStrategyFamily: String((data.parsedStrategy.strategySpec as Record<string, unknown> | undefined)?.strategyType || data.parsedStrategy.strategyKind || ''),
      executable: Boolean(data.parsedStrategy.executable),
      normalizationState: data.parsedStrategy.normalizationState,
      assumptions: data.parsedStrategy.assumptions,
      assumptionGroups: data.parsedStrategy.assumptionGroups,
      detectedStrategyFamily,
      unsupportedReason: data.parsedStrategy.unsupportedReason,
      unsupportedDetails: data.parsedStrategy.unsupportedDetails,
      unsupportedExtensions,
      coreIntentSummary,
      interpretationConfidence,
      supportedPortionSummary: data.parsedStrategy.supportedPortionSummary,
      rewriteSuggestions: data.parsedStrategy.rewriteSuggestions,
      parseWarnings: data.parsedStrategy.parseWarnings,
      confidence: data.parsedConfidence ?? data.parsedStrategy.confidence ?? 0,
      needsConfirmation: data.needsConfirmation,
      ambiguities: data.warnings,
      summary: parsedStrategySummary,
      maxLookback: data.parsedStrategy.maxLookback,
    });
    setRuleParseSignature(buildRuleParseSignature({
      code: data.code,
      strategyText: data.strategyText,
      startDate: data.startDate || '',
      endDate: data.endDate || '',
      initialCapital: String(data.initialCapital || 100000),
      feeBps: String(data.feeBps ?? 0),
      slippageBps: String(data.slippageBps ?? 0),
    }));
    setRuleConfirmed(true);
    setRuleCurrentStep('strategy');
    setAppliedRewriteText(null);
  }, []);

  const fetchResults = useCallback(async (page = 1, code?: string, windowBars?: number, runId?: number | null) => {
    setIsLoadingResults(true);
    try {
      const response = await backtestApi.getResults({
        code: code || undefined,
        evalWindowDays: windowBars,
        runId: runId || undefined,
        page,
        limit: HISTORICAL_PAGE_SIZE,
      });
      setResults(response.items);
      setTotalResults(response.total);
      setCurrentPage(response.page);
      setPageError(null);
    } catch (error) {
      setPageError(getParsedApiError(error));
    } finally {
      setIsLoadingResults(false);
    }
  }, []);

  const fetchHistory = useCallback(async (page = 1, code?: string) => {
    setIsLoadingHistory(true);
    try {
      const response = await backtestApi.getHistory({ code: code || undefined, page, limit: HISTORY_PAGE_SIZE });
      setHistoryItems(response.items);
      setHistoryTotal(response.total);
      setHistoryPage(response.page);
      setHistoryError(null);
    } catch (error) {
      setHistoryError(getParsedApiError(error));
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  const fetchSampleStatus = useCallback(async (code?: string) => {
    if (!code) {
      setSampleStatus(null);
      setSampleStatusError(null);
      return;
    }
    setIsLoadingSampleStatus(true);
    try {
      const response = await backtestApi.getSampleStatus(code);
      setSampleStatus(response);
      setSampleStatusError(null);
    } catch (error) {
      setSampleStatus(null);
      setSampleStatusError(getParsedApiError(error));
    } finally {
      setIsLoadingSampleStatus(false);
    }
  }, []);

  const fetchRuleHistory = useCallback(async (page = 1, code?: string) => {
    setIsLoadingRuleHistory(true);
    try {
      const response = await backtestApi.getRuleBacktestRuns({ code: code || undefined, page, limit: RULE_HISTORY_PAGE_SIZE });
      setRuleHistoryItems(response.items);
      setRuleHistoryTotal(response.total);
      setRuleHistoryPage(response.page);
      setRuleHistoryError(null);
    } catch (error) {
      setRuleHistoryError(getParsedApiError(error));
    } finally {
      setIsLoadingRuleHistory(false);
    }
  }, []);

  useEffect(() => {
    const state = location.state as BacktestPageLocationState | null;
    const draftRun = state?.draftRun;
    if (draftRun) {
      applyRuleRunDraft(draftRun);
      return;
    }

    const prefillCode = state?.prefillCode?.trim().toUpperCase();
    if (!prefillCode) return;

    setActiveModule('rule');
    setCodeFilter(prefillCode);
  }, [applyRuleRunDraft, location.state]);

  const fetchPerformance = useCallback(async (code?: string, windowBars?: number, options: { showNotice?: boolean } = {}) => {
    const { showNotice = true } = options;
    setIsLoadingPerf(true);
    const notices: string[] = [];
    let hasDanger = false;

    try {
      const overall = await backtestApi.getOverallPerformance(windowBars);
      setOverallPerf(overall);
      if (overall == null && showNotice) notices.push('暂无整体历史分析评估汇总。');
    } catch (error) {
      setOverallPerf(null);
      hasDanger = true;
      if (showNotice) notices.push(getParsedApiError(error).message);
    }

    if (code) {
      try {
        const stock = await backtestApi.getStockPerformance(code, windowBars);
        setStockPerf(stock);
        if (stock == null && showNotice) notices.push(`暂无 ${code} 的单股历史分析评估汇总。`);
      } catch (error) {
        setStockPerf(null);
        hasDanger = true;
        if (showNotice) notices.push(getParsedApiError(error).message);
      }
    } else {
      setStockPerf(null);
    }

    if (showNotice && notices.length > 0) {
      setPerformanceNotice({ tone: hasDanger ? 'danger' : 'warning', message: notices.join(' ') });
    } else if (showNotice) {
      setPerformanceNotice(null);
    }

    setIsLoadingPerf(false);
  }, []);

  useEffect(() => {
    const init = async () => {
      try {
        const overall = await backtestApi.getOverallPerformance();
        setOverallPerf(overall);
        const defaultWindow = overall?.evalWindowDays;
        if (defaultWindow) setEvaluationBars(String(defaultWindow));
        setPerformanceNotice(null);
      } catch (error) {
        setPerformanceNotice({
          tone: 'danger',
          message: getParsedApiError(error).message,
        });
      } finally {
        void fetchResults(1, undefined, undefined, null);
        void fetchHistory(1, undefined);
        void fetchRuleHistory(1, undefined);
      }
    };
    void init();
  }, [fetchHistory, fetchResults, fetchRuleHistory]);

  const handleFilter = () => {
    const code = normalizedCode || undefined;
    const windowBars = parsePositiveInt(evaluationBars, 10);
    setSelectedRunId(null);
    setHistoryPage(1);
    setCurrentPage(1);
    setRuleHistoryPage(1);
    setPerformanceNotice(null);
    setSelectedRuleRunId(null);
    void fetchResults(1, code, windowBars, null);
    void fetchHistory(1, code);
    void fetchSampleStatus(code);
    void fetchPerformance(code, windowBars, { showNotice: true });
    void fetchRuleHistory(1, code);
  };

  const handleRunHistoricalEvaluation = async () => {
    setIsRunningHistoricalEval(true);
    setRunResult(null);
    setRunError(null);
    setPrepareResult(null);
    setPrepareError(null);
    try {
      const windowBars = parsePositiveInt(evaluationBars, 10);
      const maturityCalendarDays = parsePositiveInt(maturityDays, 14, 0);
      const response = await backtestApi.run({
        code: normalizedCode || undefined,
        force: forceReplaceResults,
        evalWindowDays: windowBars,
        minAgeDays: maturityCalendarDays,
      });
      setRunResult(response);
      setSelectedRunId(response.runId ?? null);
      await Promise.all([
        fetchResults(1, normalizedCode || undefined, windowBars, response.runId ?? null),
        fetchHistory(1, normalizedCode || undefined),
        fetchSampleStatus(normalizedCode || undefined),
      ]);
      await fetchPerformance(normalizedCode || undefined, windowBars, { showNotice: true });
    } catch (error) {
      setRunError(getParsedApiError(error));
    } finally {
      setIsRunningHistoricalEval(false);
    }
  };

  const handlePrepareSamples = async (options: { forceRefresh?: boolean } = {}) => {
    if (!normalizedCode) {
      setPrepareError({
        title: '缺少股票代码',
        message: '请先输入股票代码，再准备历史分析评估样本。',
        rawMessage: '请先输入股票代码，再准备历史分析评估样本。',
        category: 'missing_params',
      });
      return;
    }

    setIsPreparingSamples(true);
    setPrepareResult(null);
    setPrepareError(null);
    try {
      const response = await backtestApi.prepareSamples({
        code: normalizedCode,
        sampleCount: resolvedSampleCount,
        evalWindowDays: parsePositiveInt(evaluationBars, 10),
        minAgeDays: parsePositiveInt(maturityDays, 14, 0),
        forceRefresh: options.forceRefresh || false,
      });
      setPrepareResult(response);
      await Promise.all([
        fetchSampleStatus(normalizedCode),
        fetchHistory(1, normalizedCode),
      ]);
    } catch (error) {
      setPrepareError(getParsedApiError(error));
    } finally {
      setIsPreparingSamples(false);
    }
  };

  const handleRebuildSamples = async () => {
    if (!normalizedCode) {
      setPrepareError({
        title: '缺少股票代码',
        message: '请先输入股票代码，再重建历史分析评估样本。',
        rawMessage: '请先输入股票代码，再重建历史分析评估样本。',
        category: 'missing_params',
      });
      return;
    }

    setIsPreparingSamples(true);
    setPrepareResult(null);
    setPrepareError(null);
    try {
      await backtestApi.clearSamples(normalizedCode);
      await handlePrepareSamples({ forceRefresh: false });
      await fetchResults(1, normalizedCode, parsePositiveInt(evaluationBars, 10), null);
    } catch (error) {
      setPrepareError(getParsedApiError(error));
      setIsPreparingSamples(false);
    }
  };

  const handleClearSamples = async () => {
    if (!normalizedCode) {
      setPrepareError({
        title: '缺少股票代码',
        message: '请先输入股票代码，再清理历史分析评估样本。',
        rawMessage: '请先输入股票代码，再清理历史分析评估样本。',
        category: 'missing_params',
      });
      return;
    }

    setIsPreparingSamples(true);
    setPrepareError(null);
    try {
      await backtestApi.clearSamples(normalizedCode);
      setPrepareResult(null);
      setRunResult(null);
      setSelectedRunId(null);
      setResults([]);
      setTotalResults(0);
      setOverallPerf(null);
      setStockPerf(null);
      await Promise.all([
        fetchSampleStatus(normalizedCode),
        fetchHistory(1, normalizedCode),
        fetchResults(1, normalizedCode, parsePositiveInt(evaluationBars, 10), null),
      ]);
      await fetchPerformance(normalizedCode, parsePositiveInt(evaluationBars, 10), { showNotice: true });
    } catch (error) {
      setPrepareError(getParsedApiError(error));
    } finally {
      setIsPreparingSamples(false);
    }
  };

  const handleClearResults = async () => {
    if (!normalizedCode) {
      setRunError({
        title: '缺少股票代码',
        message: '请先输入股票代码，再清理历史分析评估结果。',
        rawMessage: '请先输入股票代码，再清理历史分析评估结果。',
        category: 'missing_params',
      });
      return;
    }

    setIsRunningHistoricalEval(true);
    setRunError(null);
    try {
      await backtestApi.clearResults(normalizedCode);
      setRunResult(null);
      setSelectedRunId(null);
      setResults([]);
      setTotalResults(0);
      await Promise.all([
        fetchHistory(1, normalizedCode),
        fetchResults(1, normalizedCode, parsePositiveInt(evaluationBars, 10), null),
      ]);
      await fetchPerformance(normalizedCode, parsePositiveInt(evaluationBars, 10), { showNotice: true });
    } catch (error) {
      setRunError(getParsedApiError(error));
    } finally {
      setIsRunningHistoricalEval(false);
    }
  };

  const handleOpenHistoricalRun = async (run: BacktestRunHistoryItem) => {
    setSelectedRunId(run.id);
    setCodeFilter(run.code || '');
    setEvaluationBars(String(run.evaluationWindowTradingBars || run.evalWindowDays));
    setMaturityDays(String(run.maturityCalendarDays || run.minAgeDays));
    setForceReplaceResults(false);
    setPerformanceNotice(null);
    await Promise.all([
      fetchHistory(1, run.code || undefined),
      fetchSampleStatus(run.code || undefined),
      fetchResults(1, run.code || undefined, run.evalWindowDays, run.id),
    ]);
    await fetchPerformance(run.code || undefined, run.evalWindowDays, { showNotice: true });
  };

  const handleParseRuleStrategy = async () => {
    if (!ruleStrategyText.trim()) {
      setRuleParseError({
        title: '缺少策略文本',
        message: '请输入规则策略文本后再解析。',
        rawMessage: '请输入规则策略文本后再解析。',
        category: 'missing_params',
      });
      return;
    }

    setIsParsingRuleStrategy(true);
    setRuleParseError(null);
    setRuleRunError(null);
    setAppliedRewriteText(null);
    try {
      const response = await backtestApi.parseRuleStrategy({
        code: normalizedCode || undefined,
        strategyText: ruleStrategyText,
        startDate: ruleStartDate || undefined,
        endDate: ruleEndDate || undefined,
        initialCapital: Number.parseFloat(ruleInitialCapital) || undefined,
        feeBps: Number.parseFloat(ruleFeeBps) || 0,
        slippageBps: Number.parseFloat(ruleSlippageBps) || 0,
      });
      setRuleParsedStrategy(response);
      const strategySpec = getStrategyPreviewSpec(response);
      const parsedSymbol = getPeriodicString(strategySpec, 'symbol');
      const parsedStartDate = getPeriodicString(strategySpec, 'start_date');
      const parsedEndDate = getPeriodicString(strategySpec, 'end_date');
      const parsedInitialCapital = getPeriodicNumber(strategySpec, 'initial_capital');
      const resolvedCode = parsedSymbol !== '--' ? parsedSymbol.toUpperCase() : normalizedCode;
      const resolvedStartDate = parsedStartDate !== '--' ? parsedStartDate : ruleStartDate;
      const resolvedEndDate = parsedEndDate !== '--' ? parsedEndDate : ruleEndDate;
      const resolvedInitialCapital = parsedInitialCapital != null ? String(parsedInitialCapital) : ruleInitialCapital;
      if (parsedSymbol !== '--') setCodeFilter(resolvedCode);
      if (parsedStartDate !== '--') setRuleStartDate(parsedStartDate);
      if (parsedEndDate !== '--') setRuleEndDate(parsedEndDate);
      if (parsedInitialCapital != null) setRuleInitialCapital(String(parsedInitialCapital));
      setRuleConfirmed(false);
      setSelectedRuleRunId(null);
      setRuleParseSignature(buildRuleParseSignature({
        code: resolvedCode,
        strategyText: ruleStrategyText,
        startDate: resolvedStartDate,
        endDate: resolvedEndDate,
        initialCapital: resolvedInitialCapital,
        feeBps: ruleFeeBps,
        slippageBps: ruleSlippageBps,
      }));
      setRuleCurrentStep('strategy');
      await fetchRuleHistory(1, resolvedCode || undefined);
    } catch (error) {
      setRuleParseError(getParsedApiError(error));
    } finally {
      setIsParsingRuleStrategy(false);
    }
  };

  const handleApplyRuleRewriteSuggestion = useCallback((value: string) => {
    setRuleStrategyText(value);
    setRuleParsedStrategy(null);
    setRuleParseError(null);
    setRuleRunError(null);
    setRuleConfirmed(false);
    setRuleCurrentStep('setup');
    setRuleParseSignature(null);
    setAppliedRewriteText(value);
  }, []);

  const handleRuleStrategyTextChange = useCallback((value: string) => {
    setRuleStrategyText(value);
    if (appliedRewriteText != null) {
      setAppliedRewriteText(null);
    }
  }, [appliedRewriteText]);

  const handleRunRuleBacktest = async () => {
    const strategySpec = getStrategyPreviewSpec(ruleParsedStrategy);
    const parsedSymbol = getPeriodicString(strategySpec, 'symbol');
    const resolvedCode = normalizedCode || (parsedSymbol !== '--' ? parsedSymbol.toUpperCase() : '');
    if (!resolvedCode) {
      setRuleRunError({
        title: '缺少股票代码',
        message: '请输入股票代码后再提交规则回测。',
        rawMessage: '请输入股票代码后再提交规则回测。',
        category: 'missing_params',
      });
      return;
    }
    if (!ruleParsedStrategy) {
      setRuleRunError({
        title: '需要先解析策略',
        message: '请先解析并确认规则结构，再提交确定性规则回测。',
        rawMessage: '请先解析并确认规则结构，再提交确定性规则回测。',
        category: 'validation_error',
      });
      return;
    }
    if (isRuleParseStale) {
      setRuleRunError({
        title: '解析结果已过期',
        message: '当前输入已经变更。请重新解析后再提交回测。',
        rawMessage: '当前输入已经变更。请重新解析后再提交回测。',
        category: 'validation_error',
      });
      return;
    }
    if (!ruleConfirmed) {
      setRuleRunError({
        title: '需要确认解析结果',
        message: '请确认归一化规则后再提交回测。',
        rawMessage: '请确认归一化规则后再提交回测。',
        category: 'validation_error',
      });
      return;
    }
    if (!ruleStartDate || !ruleEndDate) {
      setRuleRunError({
        title: '缺少回测区间',
        message: '请填写开始日期和结束日期后再提交回测。',
        rawMessage: '请填写开始日期和结束日期后再提交回测。',
        category: 'validation_error',
      });
      return;
    }
    if (ruleStartDate > ruleEndDate) {
      setRuleRunError({
        title: '日期区间无效',
        message: '开始日期不能晚于结束日期。',
        rawMessage: '开始日期不能晚于结束日期。',
        category: 'validation_error',
      });
      return;
    }
    if (ruleBenchmarkMode === 'custom_code' && !ruleBenchmarkCode.trim()) {
      setRuleRunError({
        title: '缺少自定义基准代码',
        message: '选择自定义代码后，请先填写基准代码。',
        rawMessage: '选择自定义代码后，请先填写基准代码。',
        category: 'validation_error',
      });
      return;
    }

    setIsSubmittingRuleBacktest(true);
    setRuleRunError(null);
    try {
      const response = await backtestApi.runRuleBacktest({
        code: resolvedCode,
        strategyText: ruleStrategyText,
        parsedStrategy: ruleParsedStrategy.parsedStrategy,
        startDate: ruleStartDate,
        endDate: ruleEndDate,
        lookbackBars: parsePositiveInt(ruleLookbackBars, 252, 10),
        initialCapital: Number.parseFloat(ruleInitialCapital) || 100000,
        feeBps: Number.parseFloat(ruleFeeBps) || 0,
        slippageBps: Number.parseFloat(ruleSlippageBps) || 0,
        benchmarkMode: ruleBenchmarkMode,
        benchmarkCode: ruleBenchmarkMode === 'custom_code'
          ? ruleBenchmarkCode.trim().toUpperCase()
          : undefined,
        confirmed: true,
        waitForCompletion: false,
      });
      setSelectedRuleRunId(response.id);
      void fetchRuleHistory(1, resolvedCode);
      navigate(`/backtest/results/${response.id}`, { state: { initialRun: response } });
    } catch (error) {
      setRuleRunError(getParsedApiError(error));
    } finally {
      setIsSubmittingRuleBacktest(false);
    }
  };

  const handleOpenRuleRun = (run: RuleBacktestHistoryItem) => {
    setSelectedRuleRunId(run.id);
    setCodeFilter(run.code);
    navigate(`/backtest/results/${run.id}`);
  };

  const handleResultsPageChange = (page: number) => {
    void fetchResults(page, normalizedCode || undefined, parsePositiveInt(evaluationBars, 10), selectedRunId);
  };

  const handleCodeKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') handleFilter();
  };

  const handleRuleCodeKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter') return;
    const nextCode = event.currentTarget.value.trim().toUpperCase();
    setRuleHistoryPage(1);
    void fetchRuleHistory(1, nextCode || undefined);
  };

  const resetRuleFlow = useCallback(() => {
    setRuleParsedStrategy(null);
    setRuleConfirmed(false);
    setRuleRunError(null);
    setRuleParseError(null);
    setRuleParseSignature(null);
    setRuleCurrentStep('symbol');
    setAppliedRewriteText(null);
    setRuleBenchmarkMode('auto');
    setRuleBenchmarkCode('');
  }, []);

  return (
    <div className="theme-page-transition backtest-v1-page workspace-page--backtest" data-testid="backtest-v1-page">
      <WorkspacePageHeader
        eyebrow="WolfyStock"
        title="回测"
        description={`配置页现在只负责发起确定性回测，不再内嵌完整结果分析。普通模式提供引导式配置，专业模式提供密集控制；完整指标、图表、审计和导出统一落在独立结果页。当前基准默认按市场自动选择（${getBenchmarkModeLabel(ruleBenchmarkMode, normalizedCode, ruleBenchmarkCode)}）。`}
        className="backtest-v1-header"
        contentClassName="backtest-v1-header__layout"
        descriptionClassName="backtest-v1-header__description"
        actions={(
          <div className="backtest-header-toggles">
            <div className="backtest-mode-toggle" role="tablist" aria-label="回测模式">
              <button
                type="button"
                role="tab"
                aria-selected={activeModule === 'rule'}
                className={`backtest-mode-toggle__button${activeModule === 'rule' ? ' is-active' : ''}`}
                onClick={() => setActiveModule('rule')}
              >
                确定性回测
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeModule === 'historical'}
                className={`backtest-mode-toggle__button${activeModule === 'historical' ? ' is-active' : ''}`}
                onClick={() => setActiveModule('historical')}
              >
                历史评估
              </button>
            </div>
            <div className="backtest-mode-toggle" role="tablist" aria-label="控制面板模式">
              <button
                type="button"
                role="tab"
                aria-selected={controlPanelMode === 'normal'}
                className={`backtest-mode-toggle__button${controlPanelMode === 'normal' ? ' is-active' : ''}`}
                onClick={() => setControlPanelMode('normal')}
              >
                普通
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={controlPanelMode === 'professional'}
                className={`backtest-mode-toggle__button${controlPanelMode === 'professional' ? ' is-active' : ''}`}
                onClick={() => setControlPanelMode('professional')}
              >
                专业
              </button>
            </div>
          </div>
        )}
      />

      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={activeModule}
          className={`backtest-v1-stage backtest-v1-stage--${activeModule}`}
          data-testid="backtest-v1-stage"
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={WORKBENCH_PANEL_TRANSITION}
        >
          {activeModule === 'historical' ? (
            <HistoricalEvaluationPanel
              normalizedCode={normalizedCode}
              codeFilter={codeFilter}
              onCodeChange={setCodeFilter}
              onCodeEnter={handleCodeKeyDown}
              evaluationBars={evaluationBars}
              onEvaluationBarsChange={setEvaluationBars}
              maturityDays={maturityDays}
              onMaturityDaysChange={setMaturityDays}
              samplePreset={samplePreset}
              onSamplePresetChange={setSamplePreset}
              customSampleCount={customSampleCount}
              onCustomSampleCountChange={setCustomSampleCount}
              resolvedSampleCount={resolvedSampleCount}
              forceReplaceResults={forceReplaceResults}
              onForceReplaceResultsChange={setForceReplaceResults}
              onFilter={handleFilter}
              onPrepareSamples={() => handlePrepareSamples({ forceRefresh: false })}
              onRebuildSamples={handleRebuildSamples}
              onClearSamples={handleClearSamples}
              onRunEvaluation={handleRunHistoricalEvaluation}
              onClearResults={handleClearResults}
              isPreparingSamples={isPreparingSamples}
              isRunningHistoricalEval={isRunningHistoricalEval}
              runResult={runResult}
              runError={runError}
              prepareResult={prepareResult}
              prepareError={prepareError}
              sampleStatus={sampleStatus}
              sampleStatusError={sampleStatusError}
              historicalAssumptions={historicalAssumptions}
              historicalSourceMetadata={historicalSourceMetadata}
              historicalSampleTransparency={historicalSampleTransparency}
              isLoadingSampleStatus={isLoadingSampleStatus}
              isLoadingPerf={isLoadingPerf}
              historicalSummaryItems={historicalSummaryItems}
              performanceNotice={performanceNotice}
              results={results}
              totalResults={totalResults}
              currentPage={currentPage}
              pageSize={HISTORICAL_PAGE_SIZE}
              onChangeResultsPage={handleResultsPageChange}
              pageError={pageError}
              isLoadingResults={isLoadingResults}
              historyItems={historyItems}
              historyTotal={historyTotal}
              historyPage={historyPage}
              historyPageSize={HISTORY_PAGE_SIZE}
              onChangeHistoryPage={(page) => {
                setHistoryPage(page);
                void fetchHistory(page, normalizedCode || undefined);
              }}
              onOpenHistoricalRun={handleOpenHistoricalRun}
              selectedRunId={selectedRunId}
              historyError={historyError}
              isLoadingHistory={isLoadingHistory}
              panelMode={controlPanelMode}
            />
          ) : (
            <DeterministicBacktestFlow
              code={normalizedCode}
              onCodeChange={setCodeFilter}
              onCodeEnter={handleRuleCodeKeyDown}
              strategyText={ruleStrategyText}
              onStrategyTextChange={handleRuleStrategyTextChange}
              startDate={ruleStartDate}
              onStartDateChange={setRuleStartDate}
              endDate={ruleEndDate}
              onEndDateChange={setRuleEndDate}
              initialCapital={ruleInitialCapital}
              onInitialCapitalChange={setRuleInitialCapital}
              lookbackBars={ruleLookbackBars}
              onLookbackBarsChange={setRuleLookbackBars}
              feeBps={ruleFeeBps}
              onFeeBpsChange={setRuleFeeBps}
              slippageBps={ruleSlippageBps}
              onSlippageBpsChange={setRuleSlippageBps}
              benchmarkMode={ruleBenchmarkMode}
              onBenchmarkModeChange={setRuleBenchmarkMode}
              benchmarkCode={ruleBenchmarkCode}
              onBenchmarkCodeChange={setRuleBenchmarkCode}
              parsedStrategy={ruleParsedStrategy}
              confirmed={ruleConfirmed}
              onToggleConfirmed={setRuleConfirmed}
              isParsing={isParsingRuleStrategy}
              parseError={ruleParseError}
              onParse={handleParseRuleStrategy}
              isSubmitting={isSubmittingRuleBacktest}
              runError={ruleRunError}
              onRun={handleRunRuleBacktest}
              onReset={resetRuleFlow}
              historyItems={ruleHistoryItems}
              historyTotal={ruleHistoryTotal}
              historyPage={ruleHistoryPage}
              selectedRunId={selectedRuleRunId}
              isLoadingHistory={isLoadingRuleHistory}
              historyError={ruleHistoryError}
              onRefreshHistory={() => void fetchRuleHistory(1, normalizedCode || undefined)}
              onOpenHistoryRun={handleOpenRuleRun}
              previewAssumptions={previewRuleAssumptions}
              currentStep={ruleCurrentStep}
              onStepChange={setRuleCurrentStep}
              parseStale={isRuleParseStale}
              onApplyRewriteSuggestion={handleApplyRuleRewriteSuggestion}
              appliedRewriteText={appliedRewriteText}
              panelMode={controlPanelMode}
            />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
};

export default BacktestPage;
