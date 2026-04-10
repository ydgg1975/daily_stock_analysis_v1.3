import type React from 'react';
import { useCallback, useEffect, useRef } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { ApiErrorAlert, Badge, Button, Card } from '../../components/common';
import type { ParsedApiError } from '../../api/error';
import type {
  AssumptionMap,
  RuleBacktestHistoryItem,
  RuleBacktestParseResponse,
} from '../../types/backtest';
import {
  AssumptionList,
  Banner,
  Disclosure,
  RULE_BENCHMARK_OPTIONS,
  RuleRunsTable,
  SectionEyebrow,
  buildPeriodicAssumptions,
  formatCashPolicy,
  formatDraftOrder,
  formatExecutionPriceBasis,
  formatExitPolicy,
  formatNumber,
  getBenchmarkModeLabel,
  getPeriodicNumber,
  getPeriodicString,
  type RuleBenchmarkMode,
  getStrategyPreviewSpec,
  getStrategySpecValue,
} from './shared';

export type RuleWizardStep = 'symbol' | 'setup' | 'strategy' | 'confirm' | 'run';

type ProfessionalStep = RuleWizardStep;
type NormalStep = Exclude<RuleWizardStep, 'confirm'>;

const PROFESSIONAL_STEP_ORDER: ProfessionalStep[] = ['symbol', 'setup', 'strategy', 'confirm', 'run'];
const NORMAL_STEP_ORDER: NormalStep[] = ['symbol', 'setup', 'strategy', 'run'];

const PROFESSIONAL_STEP_LABELS: Record<ProfessionalStep, { title: string; short: string }> = {
  symbol: { title: '基础参数', short: '参数' },
  setup: { title: '策略输入', short: '输入' },
  strategy: { title: '解析确认', short: '确认' },
  confirm: { title: '执行设置', short: '执行' },
  run: { title: '运行控制', short: '运行' },
};

const NORMAL_STEP_LABELS: Record<NormalStep, { title: string; short: string }> = {
  symbol: { title: '基础参数', short: '参数' },
  setup: { title: '策略输入', short: '输入' },
  strategy: { title: '策略确认', short: '确认' },
  run: { title: '开始运行', short: '运行' },
};

const STRATEGY_EXAMPLES = [
  'MACD 金叉买入，死叉卖出',
  '5日均线上穿20日均线买入，下穿卖出',
  '从2025-01-01到2025-12-31，每月定投1000美元AAPL',
  'RSI 小于 30 买入，大于 70 卖出',
];

const FLOW_PANEL_TRANSITION = {
  duration: 0.24,
  ease: [0.22, 1, 0.36, 1] as const,
};

type ParseState = 'empty' | 'ready' | 'assumed' | 'unsupported' | 'stale';

type StrategyPreviewRow = { label: string; value: string };

function getParsedExecutable(parsed: RuleBacktestParseResponse | null): boolean {
  if (!parsed) return false;
  if (typeof parsed.executable === 'boolean') return parsed.executable;
  return Boolean(parsed.parsedStrategy.executable);
}

function getParsedNormalizationState(parsed: RuleBacktestParseResponse | null): string {
  if (!parsed) return 'pending';
  return String(parsed.normalizationState || parsed.parsedStrategy.normalizationState || 'pending');
}

function getParsedAssumptionRecords(parsed: RuleBacktestParseResponse | null): Array<Record<string, unknown>> {
  if (!parsed) return [];
  const topLevel = Array.isArray(parsed.assumptions) ? parsed.assumptions : [];
  if (topLevel.length > 0) return topLevel;
  return Array.isArray(parsed.parsedStrategy.assumptions) ? parsed.parsedStrategy.assumptions : [];
}

function getParsedAssumptionGroups(parsed: RuleBacktestParseResponse | null): Array<Record<string, unknown>> {
  if (!parsed) return [];
  const topLevel = Array.isArray(parsed.assumptionGroups) ? parsed.assumptionGroups : [];
  if (topLevel.length > 0) return topLevel;
  return Array.isArray(parsed.parsedStrategy.assumptionGroups) ? parsed.parsedStrategy.assumptionGroups : [];
}

function getUnsupportedReason(parsed: RuleBacktestParseResponse | null): string | null {
  if (!parsed) return null;
  return String(parsed.unsupportedReason || parsed.parsedStrategy.unsupportedReason || '') || null;
}

function getUnsupportedDetails(parsed: RuleBacktestParseResponse | null): Array<Record<string, unknown>> {
  if (!parsed) return [];
  const topLevel = Array.isArray(parsed.unsupportedDetails) ? parsed.unsupportedDetails : [];
  if (topLevel.length > 0) return topLevel;
  return Array.isArray(parsed.parsedStrategy.unsupportedDetails) ? parsed.parsedStrategy.unsupportedDetails : [];
}

function getUnsupportedExtensions(parsed: RuleBacktestParseResponse | null): Array<Record<string, unknown>> {
  if (!parsed) return [];
  const topLevel = Array.isArray(parsed.unsupportedExtensions) ? parsed.unsupportedExtensions : [];
  if (topLevel.length > 0) return topLevel;
  return Array.isArray(parsed.parsedStrategy.unsupportedExtensions) ? parsed.parsedStrategy.unsupportedExtensions : [];
}

function getDetectedStrategyFamily(parsed: RuleBacktestParseResponse | null): string | null {
  if (!parsed) return null;
  return String(parsed.detectedStrategyFamily || parsed.parsedStrategy.detectedStrategyFamily || '') || null;
}

function getCoreIntentSummary(parsed: RuleBacktestParseResponse | null): string | null {
  if (!parsed) return null;
  return String(parsed.coreIntentSummary || parsed.parsedStrategy.coreIntentSummary || '') || null;
}

function getSupportedPortionSummary(parsed: RuleBacktestParseResponse | null): string | null {
  if (!parsed) return null;
  return String(parsed.supportedPortionSummary || parsed.parsedStrategy.supportedPortionSummary || '') || null;
}

function getRewriteSuggestions(parsed: RuleBacktestParseResponse | null): Array<Record<string, unknown>> {
  if (!parsed) return [];
  const topLevel = Array.isArray(parsed.rewriteSuggestions) ? parsed.rewriteSuggestions : [];
  if (topLevel.length > 0) return topLevel;
  return Array.isArray(parsed.parsedStrategy.rewriteSuggestions) ? parsed.parsedStrategy.rewriteSuggestions : [];
}

function getParseWarnings(parsed: RuleBacktestParseResponse | null): Array<Record<string, unknown>> {
  if (!parsed) return [];
  const topLevel = Array.isArray(parsed.parseWarnings) ? parsed.parseWarnings : [];
  if (topLevel.length > 0) return topLevel;
  return Array.isArray(parsed.parsedStrategy.parseWarnings) ? parsed.parsedStrategy.parseWarnings : [];
}

function hasMeaningfulNode(node: unknown): boolean {
  if (!node || typeof node !== 'object') return false;
  const candidate = node as { type?: string; rules?: unknown[] };
  if (candidate.type === 'comparison') return true;
  if (candidate.type === 'group' && Array.isArray(candidate.rules)) {
    return candidate.rules.some((child) => hasMeaningfulNode(child));
  }
  return false;
}

function formatStrategyFamily(strategyType: string): string {
  if (strategyType === 'periodic_accumulation') return '区间定投';
  if (strategyType === 'moving_average_crossover') return '均线交叉';
  if (strategyType === 'macd_crossover') return 'MACD 交叉';
  if (strategyType === 'rsi_threshold') return 'RSI 阈值';
  if (strategyType === 'rule_conditions') return '条件规则';
  return strategyType || '--';
}

function getStrategyTypeLabel(parsed: RuleBacktestParseResponse | null): string {
  const spec = getStrategyPreviewSpec(parsed);
  const normalizedStrategyType = String(getStrategySpecValue(spec, ['strategy_type']) || '');
  const parsedStrategyKind = String(parsed?.parsedStrategy.strategyKind || '');
  const detectedStrategyFamily = String(getDetectedStrategyFamily(parsed) || '');
  const strategyType = normalizedStrategyType
    || (parsedStrategyKind && parsedStrategyKind !== 'rule_conditions' ? parsedStrategyKind : '')
    || detectedStrategyFamily
    || parsedStrategyKind;
  return formatStrategyFamily(strategyType);
}

function formatFrequencyLabel(spec: Record<string, unknown> | undefined, parsed: RuleBacktestParseResponse | null): string {
  const strategyType = String(getStrategySpecValue(spec, ['strategy_type']) || parsed?.parsedStrategy.strategyKind || '');
  if (strategyType === 'periodic_accumulation') {
    const frequency = getPeriodicString(spec, 'execution_frequency');
    if (frequency === 'daily') return '每个交易日';
    if (frequency === 'weekly') return '每周';
    if (frequency === 'monthly') return '每月';
    return frequency === '--' ? '--' : frequency;
  }
  return '按日线信号';
}

function getFillTimingLabel(spec: Record<string, unknown> | undefined, parsed: RuleBacktestParseResponse | null): string {
  const strategyType = String(getStrategySpecValue(spec, ['strategy_type']) || parsed?.parsedStrategy.strategyKind || '');
  if (strategyType === 'periodic_accumulation') return formatExecutionPriceBasis(spec);
  return '下一根开盘价';
}

function getSignalTimingLabel(spec: Record<string, unknown> | undefined, parsed: RuleBacktestParseResponse | null): string {
  const strategyType = String(getStrategySpecValue(spec, ['strategy_type']) || parsed?.parsedStrategy.strategyKind || '');
  if (strategyType === 'periodic_accumulation') return '按计划触发';
  return '收盘后判定';
}

function getPositionBehaviorLabel(spec: Record<string, unknown> | undefined, parsed: RuleBacktestParseResponse | null): string {
  const strategyType = String(getStrategySpecValue(spec, ['strategy_type']) || parsed?.parsedStrategy.strategyKind || '');
  if (strategyType === 'periodic_accumulation') return '持续累积仓位';
  if (strategyType === 'moving_average_crossover' || strategyType === 'macd_crossover' || strategyType === 'rsi_threshold') {
    return '单标的多头 / 单次满仓 / 最多一笔持仓';
  }
  return '单一多头仓位';
}

function formatStrategyCondition(spec: Record<string, unknown> | undefined, parsed: RuleBacktestParseResponse | null, side: 'entry' | 'exit'): string {
  const strategyType = String(getStrategySpecValue(spec, ['strategy_type']) || parsed?.parsedStrategy.strategyKind || '');
  if (strategyType === 'periodic_accumulation') {
    return side === 'entry' ? formatDraftOrder(spec) : formatExitPolicy(spec);
  }
  if (strategyType === 'moving_average_crossover') {
    const fastPeriod = getStrategySpecValue(spec, ['signal', 'fast_period']);
    const slowPeriod = getStrategySpecValue(spec, ['signal', 'slow_period']);
    const fastType = String(getStrategySpecValue(spec, ['signal', 'fast_type']) || 'simple');
    const slowType = String(getStrategySpecValue(spec, ['signal', 'slow_type']) || 'simple');
    const fastLabel = `${fastType === 'ema' ? 'EMA' : 'SMA'}${fastPeriod ?? '--'}`;
    const slowLabel = `${slowType === 'ema' ? 'EMA' : 'SMA'}${slowPeriod ?? '--'}`;
    return `${fastLabel} ${side === 'entry' ? '上穿' : '下穿'} ${slowLabel}`;
  }
  if (strategyType === 'macd_crossover') {
    const fastPeriod = getStrategySpecValue(spec, ['signal', 'fast_period']) ?? 12;
    const slowPeriod = getStrategySpecValue(spec, ['signal', 'slow_period']) ?? 26;
    const signalPeriod = getStrategySpecValue(spec, ['signal', 'signal_period']) ?? 9;
    return `MACD(${fastPeriod},${slowPeriod},${signalPeriod}) ${side === 'entry' ? '金叉' : '死叉'}`;
  }
  if (strategyType === 'rsi_threshold') {
    const period = getStrategySpecValue(spec, ['signal', 'period']) ?? 14;
    const threshold = getStrategySpecValue(spec, ['signal', side === 'entry' ? 'lower_threshold' : 'upper_threshold']);
    return `RSI${period} ${side === 'entry' ? '低于' : '高于'} ${threshold ?? '--'}`;
  }
  return side === 'entry' ? parsed?.summary.entry || '--' : parsed?.summary.exit || '--';
}

function formatExecutionFrequency(spec: Record<string, unknown> | undefined): string {
  const frequency = String(getStrategySpecValue(spec, ['execution', 'frequency']) || getStrategySpecValue(spec, ['schedule', 'frequency']) || '');
  if (frequency === 'daily') return '日线';
  if (frequency === 'weekly') return '周线';
  if (frequency === 'monthly') return '月线';
  return frequency || '--';
}

function formatExecutionTimingValue(value: unknown): string {
  const text = String(value || '');
  if (text === 'bar_close') return '收盘后判定';
  if (text === 'next_bar_open') return '下一根开盘成交';
  if (text === 'session_open') return '开盘执行';
  return text || '--';
}

function formatEndBehavior(spec: Record<string, unknown> | undefined): string {
  const periodic = formatExitPolicy(spec);
  if (periodic !== '--') return periodic;
  const policy = String(getStrategySpecValue(spec, ['end_behavior', 'policy']) || '');
  if (policy === 'liquidate_at_end') return '区间结束强制平仓';
  return policy || '区间结束强制平仓';
}

function formatAssumptionRecord(item: Record<string, unknown>): string {
  const label = String(item.label || item.key || '假设');
  const value = item.value == null || item.value === '' ? '' : `：${String(item.value)}`;
  const reason = String(item.reason || '').trim();
  return `${label}${value}${reason ? `。${reason}` : ''}`;
}

function buildConfirmationRows(
  parsed: RuleBacktestParseResponse | null,
  currentCode: string,
  startDate: string,
  endDate: string,
): StrategyPreviewRow[] {
  if (!parsed) return [];
  const spec = getStrategyPreviewSpec(parsed);
  const strategyType = String(getStrategySpecValue(spec, ['strategy_type']) || parsed.parsedStrategy.strategyKind || '');
  if (strategyType === 'periodic_accumulation') {
    return [
      { label: '标的', value: getPeriodicString(spec, 'symbol') || currentCode || '--' },
      { label: '策略类型', value: getStrategyTypeLabel(parsed) },
      { label: '买入条件', value: formatDraftOrder(spec) },
      { label: '卖出条件', value: formatExitPolicy(spec) },
      { label: '执行频率', value: formatFrequencyLabel(spec, parsed) },
      { label: '信号时点', value: getSignalTimingLabel(spec, parsed) },
      { label: '成交时点', value: getFillTimingLabel(spec, parsed) },
      { label: '仓位行为', value: getPositionBehaviorLabel(spec, parsed) },
      { label: '期末处理', value: formatExitPolicy(spec) },
      { label: '初始资金', value: formatNumber(getPeriodicNumber(spec, 'initial_capital')) },
      { label: '日期区间', value: `${getPeriodicString(spec, 'start_date') || startDate || '--'} -> ${getPeriodicString(spec, 'end_date') || endDate || '--'}` },
      { label: '现金策略', value: formatCashPolicy(spec) },
    ];
  }

  if (strategyType === 'moving_average_crossover' || strategyType === 'macd_crossover' || strategyType === 'rsi_threshold') {
    return [
      { label: '标的', value: String(getStrategySpecValue(spec, ['symbol']) || currentCode || '--') },
      { label: '策略类型', value: getStrategyTypeLabel(parsed) },
      { label: '买入条件', value: formatStrategyCondition(spec, parsed, 'entry') },
      { label: '卖出条件', value: formatStrategyCondition(spec, parsed, 'exit') },
      { label: '执行频率', value: formatExecutionFrequency(spec) },
      { label: '信号时点', value: formatExecutionTimingValue(getStrategySpecValue(spec, ['execution', 'signal_timing'])) },
      { label: '成交时点', value: formatExecutionTimingValue(getStrategySpecValue(spec, ['execution', 'fill_timing'])) },
      { label: '仓位行为', value: getPositionBehaviorLabel(spec, parsed) },
      { label: '期末处理', value: formatEndBehavior(spec) },
      { label: '初始资金', value: formatNumber(Number(getStrategySpecValue(spec, ['capital', 'initial_capital']) || 0)) },
      { label: '日期区间', value: `${String(getStrategySpecValue(spec, ['date_range', 'start_date']) || startDate || '--')} -> ${String(getStrategySpecValue(spec, ['date_range', 'end_date']) || endDate || '--')}` },
    ];
  }

  const detectedFamily = getDetectedStrategyFamily(parsed);
  const coreIntentSummary = getCoreIntentSummary(parsed) || getSupportedPortionSummary(parsed);
  const unsupportedExtensions = getUnsupportedExtensions(parsed)
    .map((item) => String(item.title || item.message || '').trim())
    .filter(Boolean)
    .slice(0, 2)
    .join(' / ');

  return [
    { label: '标的', value: currentCode || '--' },
    { label: '核心策略', value: detectedFamily ? formatStrategyFamily(detectedFamily) : getStrategyTypeLabel(parsed) },
    { label: '核心意图', value: coreIntentSummary || parsed.summary.strategy || '--' },
    { label: '买入条件', value: parsed.summary.entry || '--' },
    { label: '卖出条件', value: parsed.summary.exit || '--' },
    ...(unsupportedExtensions ? [{ label: '不支持扩展', value: unsupportedExtensions }] : []),
    { label: '周期', value: parsed.parsedStrategy.timeframe || 'daily' },
    { label: '日期区间', value: `${startDate || '--'} -> ${endDate || '--'}` },
  ];
}

function getUnsupportedMessages(parsed: RuleBacktestParseResponse): string[] {
  const details = getUnsupportedDetails(parsed);
  if (details.length > 0) {
    return details.slice(0, 3).map((item) => String(item.message || item.title || '当前不支持。'));
  }
  const unsupportedReason = getUnsupportedReason(parsed);
  if (unsupportedReason) {
    return [
      unsupportedReason,
      '请补齐关键字段，或改写成当前已支持的确定性单标的规则。',
    ];
  }
  const messages = parsed.ambiguities
    .slice(0, 3)
    .map((item) => String(item.message || item.suggestion || '').trim())
    .filter(Boolean);

  if (messages.length > 0) return messages;
  return ['当前输入还没有被归一化成可执行的确定性规则。', '请收紧表达，或改用当前已支持的单标的区间定投 / 简单条件规则。'];
}

function getParseState(parsed: RuleBacktestParseResponse | null, parseStale: boolean): ParseState {
  if (!parsed) return 'empty';
  if (parseStale) return 'stale';

  const normalizationState = getParsedNormalizationState(parsed);
  if (normalizationState === 'ready') return 'ready';
  if (normalizationState === 'assumed') return 'assumed';
  if (normalizationState === 'unsupported') return 'unsupported';

  const spec = getStrategyPreviewSpec(parsed);
  const strategyType = String(getStrategySpecValue(spec, ['strategy_type']) || parsed.parsedStrategy.strategyKind || '');
  const executable = getParsedExecutable(parsed) || strategyType === 'periodic_accumulation'
    || (strategyType === 'rule_conditions' && hasMeaningfulNode(parsed.parsedStrategy.entry) && hasMeaningfulNode(parsed.parsedStrategy.exit));
  if (!executable) return 'unsupported';

  const unsupportedCodes = new Set(['missing_symbol', 'unknown_operand', 'unparsed_atom', 'missing_exit', 'empty_rule']);
  const hasUnsupportedAmbiguity = parsed.ambiguities.some((item) => unsupportedCodes.has(String(item.code || '')));
  if (hasUnsupportedAmbiguity) return 'unsupported';

  if (parsed.needsConfirmation || parsed.ambiguities.length > 0 || parsed.confidence < 0.9) return 'assumed';
  return 'ready';
}

function getParseStateMeta(parseState: ParseState): { tone: 'default' | 'success' | 'warning' | 'danger' | 'info'; label: string; title: string } {
  if (parseState === 'ready') return { tone: 'success', label: '可运行', title: '已完成归一化' };
  if (parseState === 'assumed') return { tone: 'warning', label: '待确认', title: '含默认假设' };
  if (parseState === 'unsupported') return { tone: 'danger', label: '不支持', title: '当前不支持' };
  if (parseState === 'stale') return { tone: 'warning', label: '已过期', title: '解析结果已过期' };
  return { tone: 'info', label: '待解析', title: '等待解析' };
}

function StrategySpecSummaryCard({
  parsed,
  currentCode,
  startDate,
  endDate,
}: {
  parsed: RuleBacktestParseResponse | null;
  currentCode: string;
  startDate: string;
  endDate: string;
}) {
  const rows = buildConfirmationRows(parsed, currentCode, startDate, endDate);
  if (!rows.length) return <div className="product-empty-state product-empty-state--compact">暂无策略规格。</div>;

  return (
    <div className="preview-grid">
      {rows.map((row) => (
        <div key={`${row.label}-${row.value}`} className="preview-card">
          <p className="metric-card__label">{row.label}</p>
          <p className="preview-card__text">{row.value}</p>
        </div>
      ))}
    </div>
  );
}

type FlowProps = {
  code: string;
  onCodeChange: (value: string) => void;
  onCodeEnter: (event: React.KeyboardEvent<HTMLInputElement>) => void;
  strategyText: string;
  onStrategyTextChange: (value: string) => void;
  startDate: string;
  onStartDateChange: (value: string) => void;
  endDate: string;
  onEndDateChange: (value: string) => void;
  initialCapital: string;
  onInitialCapitalChange: (value: string) => void;
  lookbackBars: string;
  onLookbackBarsChange: (value: string) => void;
  feeBps: string;
  onFeeBpsChange: (value: string) => void;
  slippageBps: string;
  onSlippageBpsChange: (value: string) => void;
  benchmarkMode: RuleBenchmarkMode;
  onBenchmarkModeChange: (value: RuleBenchmarkMode) => void;
  benchmarkCode: string;
  onBenchmarkCodeChange: (value: string) => void;
  parsedStrategy: RuleBacktestParseResponse | null;
  confirmed: boolean;
  onToggleConfirmed: (value: boolean) => void;
  isParsing: boolean;
  parseError: ParsedApiError | null;
  onParse: () => Promise<void>;
  isSubmitting: boolean;
  runError: ParsedApiError | null;
  onRun: () => Promise<void>;
  onReset: () => void;
  historyItems: RuleBacktestHistoryItem[];
  historyTotal: number;
  historyPage: number;
  selectedRunId: number | null;
  isLoadingHistory: boolean;
  historyError: ParsedApiError | null;
  onRefreshHistory: () => void;
  onOpenHistoryRun: (run: RuleBacktestHistoryItem) => void;
  previewAssumptions: AssumptionMap;
  currentStep: RuleWizardStep;
  onStepChange: (step: RuleWizardStep) => void;
  parseStale: boolean;
  onApplyRewriteSuggestion: (value: string) => void;
  appliedRewriteText: string | null;
  panelMode: 'normal' | 'professional';
};

const DeterministicBacktestFlow: React.FC<FlowProps> = ({
  code,
  onCodeChange,
  onCodeEnter,
  strategyText,
  onStrategyTextChange,
  startDate,
  onStartDateChange,
  endDate,
  onEndDateChange,
  initialCapital,
  onInitialCapitalChange,
  lookbackBars,
  onLookbackBarsChange,
  feeBps,
  onFeeBpsChange,
  slippageBps,
  onSlippageBpsChange,
  benchmarkMode,
  onBenchmarkModeChange,
  benchmarkCode,
  onBenchmarkCodeChange,
  parsedStrategy,
  confirmed,
  onToggleConfirmed,
  isParsing,
  parseError,
  onParse,
  isSubmitting,
  runError,
  onRun,
  onReset,
  historyItems,
  historyTotal,
  historyPage,
  selectedRunId,
  isLoadingHistory,
  historyError,
  onRefreshHistory,
  onOpenHistoryRun,
  previewAssumptions,
  currentStep,
  onStepChange,
  parseStale,
  onApplyRewriteSuggestion,
  appliedRewriteText,
  panelMode,
}) => {
  const stepRefs = useRef<Partial<Record<RuleWizardStep, HTMLDivElement | null>>>({});
  const setStepRef = useCallback(
    (step: RuleWizardStep) => (node: HTMLDivElement | null) => {
      stepRefs.current[step] = node;
    },
    [],
  );

  const focusStep = useCallback((step: RuleWizardStep) => {
    onStepChange(step);
    const node = stepRefs.current[step];
    node?.scrollIntoView?.({ block: 'nearest' });
    const focusable = node?.querySelector<HTMLElement>(
      'input, textarea, select, button, [tabindex]:not([tabindex="-1"])',
    );
    focusable?.focus();
  }, [onStepChange]);

  const parseState = getParseState(parsedStrategy, parseStale);
  const parseMeta = getParseStateMeta(parseState);
  const strategySpec = getStrategyPreviewSpec(parsedStrategy);
  const assumptionGroups = getParsedAssumptionGroups(parsedStrategy);
  const coreIntentSummary = getCoreIntentSummary(parsedStrategy);
  const supportedPortionSummary = getSupportedPortionSummary(parsedStrategy);
  const unsupportedExtensions = getUnsupportedExtensions(parsedStrategy);
  const rewriteSuggestions = getRewriteSuggestions(parsedStrategy);
  const parseWarnings = getParseWarnings(parsedStrategy);
  const assumptionItems = getParsedAssumptionRecords(parsedStrategy).length > 0
    ? getParsedAssumptionRecords(parsedStrategy).map((item) => formatAssumptionRecord(item))
    : (
      String(getStrategySpecValue(strategySpec, ['strategy_type']) || parsedStrategy?.parsedStrategy.strategyKind || '') === 'periodic_accumulation'
        ? buildPeriodicAssumptions(strategySpec)
        : []
    );
  const canProceedFromBaseParams = Boolean(
    startDate
    && endDate
    && initialCapital
    && startDate <= endDate
    && (benchmarkMode !== 'custom_code' || benchmarkCode.trim()),
  );
  const canProceedFromConfirm = (parseState === 'ready' || parseState === 'assumed') && confirmed && !parseStale;
  const isProfessionalMode = panelMode === 'professional';
  const professionalCurrentStepIndex = PROFESSIONAL_STEP_ORDER.indexOf(currentStep);
  const normalCurrentStep = currentStep === 'confirm' ? 'strategy' : currentStep;
  const normalCurrentStepIndex = NORMAL_STEP_ORDER.indexOf(normalCurrentStep);

  const handleStepSelect = useCallback((step: RuleWizardStep) => {
    if (isProfessionalMode) {
      focusStep(step);
      return;
    }
    onStepChange(step);
  }, [focusStep, isProfessionalMode, onStepChange]);

  const handleNormalRun = useCallback(async () => {
    onStepChange('run');
    await onRun();
  }, [onRun, onStepChange]);

  useEffect(() => {
    if (!isProfessionalMode && currentStep === 'confirm') {
      onStepChange('strategy');
    }
  }, [currentStep, isProfessionalMode, onStepChange]);

  const baseParamsSection = (
    <section
      ref={setStepRef('symbol')}
      id="backtest-control-section-symbol"
      className="backtest-control-section"
      data-testid="backtest-control-section-symbol"
      data-active={currentStep === 'symbol' ? 'true' : 'false'}
    >
      <Card title="基础参数" subtitle="步骤 1" className="product-section-card product-section-card--backtest-standard">
        {!isProfessionalMode ? (
          <p className="backtest-guided-step-helper">先确定标的、资金规模和回测区间，再进入策略输入。</p>
        ) : null}
        <div className="backtest-base-params-layout" data-testid="backtest-base-params-layout">
          <label className="product-field product-field--full">
            <span className="theme-field-label">标的代码</span>
            <input
              type="text"
              value={code}
              onChange={(event) => onCodeChange(event.target.value.toUpperCase())}
              onFocus={() => onStepChange('symbol')}
              onKeyDown={onCodeEnter}
              placeholder="例如 ORCL / AAPL / 600519"
              className="input-surface input-focus-glow product-command-input"
              aria-label="股票代码"
            />
          </label>
          <div className="backtest-date-range-grid" data-testid="backtest-base-date-range">
            <label className="product-field">
              <span className="theme-field-label">开始日期</span>
              <input
                type="date"
                value={startDate}
                onChange={(event) => onStartDateChange(event.target.value)}
                onFocus={() => onStepChange('symbol')}
                className="input-surface input-focus-glow product-command-input"
                aria-label="开始日期"
              />
            </label>
            <label className="product-field">
              <span className="theme-field-label">结束日期</span>
              <input
                type="date"
                value={endDate}
                onChange={(event) => onEndDateChange(event.target.value)}
                onFocus={() => onStepChange('symbol')}
                className="input-surface input-focus-glow product-command-input"
                aria-label="结束日期"
              />
            </label>
          </div>
          <label className="product-field product-field--full">
            <span className="theme-field-label">初始资金</span>
            <input
              type="number"
              min={1}
              value={initialCapital}
              onChange={(event) => onInitialCapitalChange(event.target.value)}
              onFocus={() => onStepChange('symbol')}
              className="input-surface input-focus-glow product-command-input"
              aria-label="初始资金"
            />
          </label>
          <label className="product-field product-field--full">
            <span className="theme-field-label">对比基准</span>
            <select
              value={benchmarkMode}
              onChange={(event) => onBenchmarkModeChange(event.target.value as RuleBenchmarkMode)}
              onFocus={() => onStepChange('symbol')}
              className="input-surface input-focus-glow product-command-input"
              aria-label="对比基准"
            >
              {RULE_BENCHMARK_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          {benchmarkMode === 'custom_code' ? (
            <label className="product-field product-field--full">
              <span className="theme-field-label">自定义基准代码</span>
              <input
                type="text"
                value={benchmarkCode}
                onChange={(event) => onBenchmarkCodeChange(event.target.value.toUpperCase())}
                onFocus={() => onStepChange('symbol')}
                placeholder="例如 QQQ / SPY / ^NDX / 000300"
                className="input-surface input-focus-glow product-command-input"
                aria-label="自定义基准代码"
              />
            </label>
          ) : null}
        </div>
        <div className="product-chip-list">
          <span className="product-chip">当前标的: {code || '--'}</span>
          <span className="product-chip">对比基准: {getBenchmarkModeLabel(benchmarkMode, code, benchmarkCode)}</span>
          <span className="product-chip">策略类型: {parsedStrategy ? getStrategyTypeLabel(parsedStrategy) : '待解析'}</span>
        </div>
        <div className="product-action-row backtest-control-actions backtest-control-actions--footer">
          <Button onClick={() => handleStepSelect('setup')} disabled={!canProceedFromBaseParams}>
            继续
          </Button>
        </div>
      </Card>
    </section>
  );

  const strategyInputSection = (
    <section
      ref={setStepRef('setup')}
      id="backtest-control-section-setup"
      className="backtest-control-section"
      data-testid="backtest-control-section-setup"
      data-active={currentStep === 'setup' ? 'true' : 'false'}
    >
      <Card title="策略输入" subtitle="步骤 2" className="product-section-card product-section-card--backtest-flow">
        {!isProfessionalMode ? (
          <p className="backtest-guided-step-helper">用自然语言描述规则，或直接点一个示例作为确定性起点。</p>
        ) : null}
        <label className="product-field product-field--full">
          <span className="theme-field-label">自然语言策略</span>
          <AnimatePresence initial={false}>
            {appliedRewriteText ? (
              <motion.div
                key="rewrite-banner"
                className="mb-4"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={FLOW_PANEL_TRANSITION}
              >
                <Banner
                  tone="info"
                  title="已应用建议改写"
                  body="策略文本已替换为建议版本。请重新解析后继续。"
                />
              </motion.div>
            ) : null}
          </AnimatePresence>
          <textarea
            aria-label="策略文本"
            value={strategyText}
            onChange={(event) => onStrategyTextChange(event.target.value)}
            onFocus={() => onStepChange('setup')}
            rows={7}
            autoFocus={Boolean(appliedRewriteText)}
            className="input-surface input-focus-glow product-command-input product-command-input--textarea"
            placeholder="例如：资金100000，从2025-01-01到2025-12-31，每天买100股ORCL，买到资金耗尽为止"
          />
        </label>

        <div className="product-chip-list wizard-example-chips">
          {STRATEGY_EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              className="product-chip product-chip--button"
              onClick={() => {
                onStepChange('setup');
                onStrategyTextChange(example);
              }}
            >
              {example}
            </button>
          ))}
        </div>

        <div className="product-action-row backtest-control-actions backtest-control-actions--footer">
          <Button variant="ghost" onClick={() => handleStepSelect('symbol')}>返回</Button>
          <Button
            variant="secondary"
            onClick={() => void onParse()}
            isLoading={isParsing}
            loadingText="解析中…"
            disabled={!canProceedFromBaseParams || !strategyText.trim()}
          >
            {appliedRewriteText ? '重新解析' : '解析策略'}
          </Button>
        </div>
        {parseError ? <ApiErrorAlert error={parseError} className="mt-4" /> : null}
      </Card>
    </section>
  );

  const executionSettingsFields = (
    <div className="product-field-grid backtest-control-grid">
      <label className="product-field">
        <span className="theme-field-label">回看范围</span>
        <input
          type="number"
          min={10}
          max={5000}
          value={lookbackBars}
          onChange={(event) => onLookbackBarsChange(event.target.value)}
          onFocus={() => onStepChange(isProfessionalMode ? 'confirm' : 'strategy')}
          className="input-surface input-focus-glow product-command-input"
          aria-label="回看范围"
        />
      </label>
      <label className="product-field">
        <span className="theme-field-label">手续费 (bp)</span>
        <input
          type="number"
          min={0}
          max={500}
          value={feeBps}
          onChange={(event) => onFeeBpsChange(event.target.value)}
          onFocus={() => onStepChange(isProfessionalMode ? 'confirm' : 'strategy')}
          className="input-surface input-focus-glow product-command-input"
          aria-label="单边手续费 (bp)"
        />
      </label>
      <label className="product-field">
        <span className="theme-field-label">滑点 (bp)</span>
        <input
          type="number"
          min={0}
          max={500}
          value={slippageBps}
          onChange={(event) => onSlippageBpsChange(event.target.value)}
          onFocus={() => onStepChange(isProfessionalMode ? 'confirm' : 'strategy')}
          className="input-surface input-focus-glow product-command-input"
          aria-label="单边滑点 (bp)"
        />
      </label>
    </div>
  );

  const parsedStrategySection = (
    <section
      ref={setStepRef('strategy')}
      id="backtest-control-section-strategy"
      className="backtest-control-section"
      data-testid="backtest-control-section-strategy"
      data-active={currentStep === 'strategy' ? 'true' : 'false'}
    >
      <Card title={isProfessionalMode ? '解析确认' : '策略确认'} subtitle="步骤 3" className="product-section-card product-section-card--backtest-standard">
        {!isProfessionalMode ? (
          <p className="backtest-guided-step-helper">确认归一化后的规则、默认假设和不支持项，再从这里进入结果页流转。</p>
        ) : null}
        <motion.div layout className="backtest-step-stage-shell">
          <AnimatePresence initial={false} mode="wait">
            {parseState === 'empty' ? (
              <motion.div
                key="parsed-empty"
                className="backtest-step-stage"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -12 }}
                transition={FLOW_PANEL_TRANSITION}
              >
                <div className="product-empty-state product-empty-state--compact">
                  先完成策略解析，再继续确认归一化结果和默认假设。
                </div>
              </motion.div>
            ) : (
              <motion.div
                key={`parsed-${parseState}-${parseStale ? 'stale' : 'current'}`}
                className="backtest-step-stage"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -12 }}
                transition={FLOW_PANEL_TRANSITION}
              >
                <div className="summary-block" data-testid="confirm-status-section">
                  <div className="summary-block__header">
                    <div>
                      <SectionEyebrow>解析状态</SectionEyebrow>
                      <h3 className="summary-block__title">确认当前解析</h3>
                    </div>
                    <Badge variant={parseMeta.tone === 'success' ? 'success' : parseMeta.tone === 'danger' ? 'danger' : parseMeta.tone === 'warning' ? 'warning' : 'default'}>
                      {parseMeta.label}
                    </Badge>
                  </div>
                  <Banner
                    tone={parseMeta.tone}
                    title={parseMeta.title}
                    body={
                      parseState === 'unsupported'
                        ? getUnsupportedMessages(parsedStrategy as RuleBacktestParseResponse)[0]
                        : parseState === 'stale'
                          ? '输入已变更。请重新解析后再继续。'
                          : parseState === 'assumed'
                            ? '策略可执行，但包含默认值或执行假设。'
                            : '策略已归一化，可直接进入独立结果页流转。'
                    }
                  />
                </div>

                <div className="summary-block mt-4" data-testid="confirm-compact-summary-section">
                  <div className="preview-grid">
                    <div className="preview-card">
                      <p className="metric-card__label">策略类型</p>
                      <p className="preview-card__text">{getStrategyTypeLabel(parsedStrategy)}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">标的</p>
                      <p className="preview-card__text">{code || '--'}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">区间</p>
                      <p className="preview-card__text">{startDate || '--'} {'->'} {endDate || '--'}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">核心意图</p>
                      <p className="preview-card__text">{coreIntentSummary || supportedPortionSummary || '待确认'}</p>
                    </div>
                  </div>
                </div>

                <Disclosure summary="查看解析细节">
                  <StrategySpecSummaryCard parsed={parsedStrategy} currentCode={code} startDate={startDate} endDate={endDate} />
                </Disclosure>

                {(supportedPortionSummary || unsupportedExtensions.length > 0 || rewriteSuggestions.length > 0) && (
                  <div className="summary-block mt-4" data-testid="confirm-guidance-section">
                    <div className="summary-block__header">
                      <div>
                        <SectionEyebrow>限制与改写</SectionEyebrow>
                        <h3 className="summary-block__title">改写建议与限制</h3>
                      </div>
                    </div>
                    {supportedPortionSummary && supportedPortionSummary !== coreIntentSummary ? (
                      <p className="product-section-copy">{supportedPortionSummary}</p>
                    ) : null}
                    {unsupportedExtensions.length > 0 ? (
                      <div className="product-chip-list mb-4">
                        {unsupportedExtensions.slice(0, 3).map((item, index) => (
                          <span key={`${String(item.code || index)}-unsupported`} className="product-chip">
                            {String(item.title || item.message || '当前不支持')}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {rewriteSuggestions.length > 0 ? (
                      <div className="product-chip-list wizard-example-chips">
                        {rewriteSuggestions.slice(0, 3).map((item, index) => {
                          const text = String(item.strategyText || '');
                          const label = String(item.label || text || `建议 ${index + 1}`);
                          if (!text) return null;
                          return (
                            <button
                              key={`${label}-${index}`}
                              type="button"
                              className="product-chip product-chip--button"
                              onClick={() => onApplyRewriteSuggestion(text)}
                            >
                              {label}: {text}
                            </button>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                )}

                {assumptionGroups.length > 0 ? (
                  <div className="summary-block mt-4" data-testid="confirm-assumptions-section">
                    <div className="summary-block__header">
                      <div>
                        <SectionEyebrow>默认假设</SectionEyebrow>
                        <h3 className="summary-block__title">假设摘要</h3>
                      </div>
                    </div>
                    <div className="preview-grid">
                      {assumptionGroups.map((group, index) => {
                        const label = String(group.label || `默认假设 ${index + 1}`);
                        const items = Array.isArray(group.items) ? group.items : [];
                        return (
                          <div key={`${label}-${index}`} className="preview-card">
                            <p className="metric-card__label">{label}</p>
                            <div className="product-chip-list">
                              {items.map((item, itemIndex) => (
                                <span key={`${label}-${itemIndex}`} className="product-chip">{formatAssumptionRecord(item as Record<string, unknown>)}</span>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : assumptionItems.length > 0 ? (
                  <Disclosure summary="默认假设">
                    <ul className="product-list">
                      {assumptionItems.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </Disclosure>
                ) : null}

                {(parseWarnings.length > 0 || (parsedStrategy && parsedStrategy.ambiguities.length > 0)) ? (
                  <Disclosure summary="提醒">
                    <ul className="product-list">
                      {parseWarnings.slice(0, 4).map((item, index) => (
                        <li key={`${String(item.code || index)}-warning`}>{String(item.message || '请人工确认。')}</li>
                      ))}
                      {parsedStrategy?.ambiguities.slice(0, 4).map((item, index) => (
                        <li key={`${String(item.code || index)}-ambiguity`}>{String(item.message || item.suggestion || '请人工确认。')}</li>
                      ))}
                    </ul>
                  </Disclosure>
                ) : null}

                {!isProfessionalMode ? (
                  <Disclosure summary="执行设置">
                    {executionSettingsFields}
                    <div className="mt-4">
                      <AssumptionList assumptions={previewAssumptions} emptyText="暂无执行默认值。" />
                    </div>
                  </Disclosure>
                ) : null}

                <label className="product-checkbox-row mt-4">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    disabled={parseState === 'unsupported' || parseState === 'stale'}
                    onChange={(event) => {
                      onStepChange('strategy');
                      onToggleConfirmed(event.target.checked);
                    }}
                  />
                  <span>我已确认当前解析结果与执行假设。</span>
                </label>

                <div className="product-action-row backtest-control-actions backtest-control-actions--footer mt-4">
                  <Button variant="ghost" onClick={() => handleStepSelect('setup')}>返回修改</Button>
                  <Button variant="secondary" onClick={() => void onParse()} disabled={isParsing || !strategyText.trim()}>
                    重新解析
                  </Button>
                  <Button
                    onClick={() => (isProfessionalMode ? handleStepSelect('confirm') : void handleNormalRun())}
                    disabled={!canProceedFromConfirm}
                    isLoading={!isProfessionalMode && isSubmitting}
                    loadingText="正在打开结果页…"
                  >
                    {isProfessionalMode ? '继续' : '确认并打开结果页'}
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </Card>
    </section>
  );

  const executionSettingsSection = (
    <section
      ref={setStepRef('confirm')}
      id="backtest-control-section-confirm"
      className="backtest-control-section"
      data-testid="backtest-control-section-confirm"
      data-active={currentStep === 'confirm' ? 'true' : 'false'}
    >
      <Card title="执行设置" subtitle="步骤 4" className="product-section-card product-section-card--backtest-standard">
        <p className="backtest-guided-step-helper">这里调整执行默认值。提交后会直接进入独立结果页进行轮询和分析。</p>
        {executionSettingsFields}
        <Disclosure summary="执行默认值">
          <AssumptionList assumptions={previewAssumptions} emptyText="暂无执行默认值。" />
        </Disclosure>
        <div className="product-action-row backtest-control-actions backtest-control-actions--footer">
          <Button variant="ghost" onClick={() => handleStepSelect('strategy')}>返回</Button>
          <Button onClick={() => handleStepSelect('run')}>继续</Button>
        </div>
      </Card>
    </section>
  );

  const runControlsSection = (
    <section
      ref={setStepRef('run')}
      id="backtest-control-section-run"
      className="backtest-control-section"
      data-testid="backtest-control-section-run"
      data-active={currentStep === 'run' ? 'true' : 'false'}
    >
      <Card title={isProfessionalMode ? '运行控制' : '开始运行'} subtitle={`步骤 ${isProfessionalMode ? '5' : '4'}`} className="product-section-card product-section-card--backtest-flow">
        <Banner
          tone={isSubmitting ? 'info' : 'default'}
          title={isSubmitting ? '正在创建回测运行' : '提交后进入独立结果页'}
          body={isSubmitting
            ? '正在提交规则回测并跳转到结果页。结果页会负责轮询状态、显示 KPI 和全宽图表工作区。'
            : '配置页只负责参数与策略确认。点击运行后会导航到 /backtest/results/:runId，由结果页承载完整分析。'}
        />
        <div className="backtest-inline-status mt-4" role="status" aria-live="polite">
          <span className="backtest-inline-status__pill" data-tone={parseMeta.tone}>解析 · {parseMeta.label}</span>
          <span className="backtest-inline-status__pill" data-tone="info">结果页 · KPI / 图表 / 审计 / 交易</span>
          {parseStale ? <span className="backtest-inline-status__pill" data-tone="warning">预览已过期</span> : null}
          {appliedRewriteText ? <span className="backtest-inline-status__pill" data-tone="info">已应用改写</span> : null}
        </div>
        <div className="preview-grid mt-4">
          <div className="preview-card">
            <p className="metric-card__label">标的</p>
            <p className="preview-card__text">{code || '--'}</p>
          </div>
          <div className="preview-card">
            <p className="metric-card__label">区间</p>
            <p className="preview-card__text">{startDate || '--'} {'->'} {endDate || '--'}</p>
          </div>
          <div className="preview-card">
            <p className="metric-card__label">初始资金</p>
            <p className="preview-card__text">{initialCapital || '--'}</p>
          </div>
          <div className="preview-card">
            <p className="metric-card__label">基准</p>
            <p className="preview-card__text">{getBenchmarkModeLabel(benchmarkMode, code, benchmarkCode)}</p>
          </div>
        </div>
        <div className="product-action-row backtest-control-actions backtest-control-actions--footer mt-4">
          <Button variant="ghost" onClick={() => handleStepSelect(isProfessionalMode ? 'confirm' : 'strategy')}>
            返回
          </Button>
          <Button
            onClick={() => void onRun()}
            isLoading={isSubmitting}
            loadingText="正在打开结果页…"
            disabled={!canProceedFromConfirm}
          >
            运行回测并打开结果页
          </Button>
          <Button variant="ghost" onClick={onReset}>重置</Button>
          <Button variant="ghost" onClick={onRefreshHistory} disabled={isLoadingHistory}>
            {isLoadingHistory ? '刷新中…' : '刷新历史'}
          </Button>
        </div>
        {runError ? <ApiErrorAlert error={runError} className="mt-4" /> : null}
      </Card>
    </section>
  );

  const professionalControlSections: Record<ProfessionalStep, React.ReactNode> = {
    symbol: baseParamsSection,
    setup: strategyInputSection,
    strategy: parsedStrategySection,
    confirm: executionSettingsSection,
    run: runControlsSection,
  };

  const normalControlSections: Record<NormalStep, React.ReactNode> = {
    symbol: baseParamsSection,
    setup: strategyInputSection,
    strategy: parsedStrategySection,
    run: runControlsSection,
  };

  const getNormalStepSummary = (step: NormalStep) => {
    if (step === 'symbol') {
      return {
        title: code || '未设置标的',
        detail: `${startDate || '--'} → ${endDate || '--'} · 资金 ${initialCapital || '--'}`,
        disabled: false,
      };
    }
    if (step === 'setup') {
      return {
        title: strategyText.trim() ? strategyText.trim().slice(0, 36) : '填写策略描述',
        detail: strategyText.trim() ? '可返回继续修改策略描述。' : '请用自然语言描述买卖条件与周期。',
        disabled: false,
      };
    }
    if (step === 'strategy') {
      return {
        title: parseMeta.title,
        detail: coreIntentSummary || supportedPortionSummary || '解析后会在这里给出确认摘要。',
        disabled: !parsedStrategy,
      };
    }
    return {
      title: isSubmitting ? '提交中' : '进入结果页',
      detail: '运行提交后会跳转到独立结果页，不再在配置页内展开完整分析。',
      disabled: !(canProceedFromConfirm || isSubmitting),
    };
  };

  const renderHistorySection = () => (
    <section className="backtest-display-section" data-testid="backtest-display-section-history">
      <Card title="历史记录" subtitle="配置页只保留入口，不内嵌完整结果分析" className="product-section-card product-section-card--backtest-secondary">
        <div className="summary-block__header">
          <div>
            <SectionEyebrow>历史记录</SectionEyebrow>
            <h3 className="summary-block__title">规则回测历史</h3>
          </div>
          <Button variant="ghost" onClick={onRefreshHistory} disabled={isLoadingHistory}>
            {isLoadingHistory ? '刷新中…' : '刷新'}
          </Button>
        </div>
        <p className="product-section-copy">点击任意历史项会打开 `/backtest/results/:runId`，由独立结果页承载相同的 KPI、图表、审计与交易分析。</p>
        {historyError ? <ApiErrorAlert error={historyError} className="mb-4" /> : null}
        <RuleRunsTable rows={historyItems} selectedRunId={selectedRunId} onOpen={onOpenHistoryRun} />
        <p className="product-footnote">共 {historyTotal} 条确定性规则回测记录。当前页 {historyPage}。</p>
      </Card>
    </section>
  );

  if (!isProfessionalMode) {
    return (
      <div className="space-y-6" data-testid="backtest-normal-wizard">
        <Card title="普通版配置" subtitle="配置页" className="product-section-card product-section-card--backtest-result">
          <p className="product-section-copy">
            普通版只负责引导你完成参数、策略与确认步骤。运行后会跳转到独立结果页，不再把完整图表分析挤在配置页里。
          </p>
        </Card>

        <nav className="backtest-normal-stepper" aria-label="确定性回测向导步骤">
          {NORMAL_STEP_ORDER.map((step, index) => {
            const stepMeta = NORMAL_STEP_LABELS[step];
            const isActive = normalCurrentStep === step;
            const isDone = index < normalCurrentStepIndex;
            const summary = getNormalStepSummary(step);
            return (
              <button
                key={step}
                type="button"
                className={`backtest-normal-step${isActive ? ' is-active' : ''}${isDone ? ' is-done' : ''}`}
                onClick={() => !summary.disabled && handleStepSelect(step)}
                disabled={summary.disabled}
              >
                <span className="backtest-normal-step__index">{index + 1}</span>
                <span className="backtest-normal-step__copy">
                  <strong>{stepMeta.title}</strong>
                  <small>{stepMeta.short}</small>
                </span>
              </button>
            );
          })}
        </nav>

        <div data-testid="backtest-normal-active-stage">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={normalCurrentStep}
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={FLOW_PANEL_TRANSITION}
            >
              {normalControlSections[normalCurrentStep]}
            </motion.div>
          </AnimatePresence>
        </div>

        <div className="grid gap-4 md:grid-cols-3" data-testid="backtest-normal-step-summaries">
          {NORMAL_STEP_ORDER.filter((step) => step !== normalCurrentStep).map((step) => {
            const stepMeta = NORMAL_STEP_LABELS[step];
            const summary = getNormalStepSummary(step);
            return (
              <button
                key={`summary-${step}`}
                type="button"
                className="backtest-normal-summary"
                data-testid={`backtest-normal-step-summary-${step}`}
                onClick={() => !summary.disabled && handleStepSelect(step)}
                disabled={summary.disabled}
              >
                <div className="backtest-normal-summary__header">
                  <span className="backtest-normal-summary__step">{stepMeta.title}</span>
                  <span className="backtest-normal-summary__short">{stepMeta.short}</span>
                </div>
                <p className="backtest-normal-summary__title">{summary.title}</p>
                <p className="backtest-normal-summary__detail">{summary.detail}</p>
              </button>
            );
          })}
        </div>

        {renderHistorySection()}
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="backtest-unified-shell" data-module="rule" data-panel-mode={panelMode}>
      <Card title="专业版配置" subtitle="配置页" className="product-section-card product-section-card--backtest-result">
        <p className="product-section-copy">
          专业版保留完整配置控制，但完整分析结果统一落在 `/backtest/results/:runId`。这里不再承载全宽图表工作区。
        </p>
      </Card>

      <nav className="backtest-control-stepper backtest-control-stepper--secondary" aria-label="确定性回测步骤">
        {PROFESSIONAL_STEP_ORDER.map((step, index) => {
          const stepMeta = PROFESSIONAL_STEP_LABELS[step];
          const isActive = currentStep === step;
          const isDone = index < professionalCurrentStepIndex;
          return (
            <button
              key={step}
              type="button"
              className={`backtest-control-step${isActive ? ' is-active' : ''}${isDone ? ' is-done' : ''}`}
              onClick={() => handleStepSelect(step)}
            >
              <span className="backtest-control-step__index">{index + 1}</span>
              <span className="backtest-control-step__copy">
                <strong>{stepMeta.title}</strong>
                <small>{stepMeta.short}</small>
              </span>
            </button>
          );
        })}
      </nav>

      <div className="space-y-6" data-testid="backtest-control-panel-expanded">
        {PROFESSIONAL_STEP_ORDER.map((step) => professionalControlSections[step])}
      </div>

      {renderHistorySection()}
    </div>
  );
};

export default DeterministicBacktestFlow;
