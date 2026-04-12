import type {
  RuleBacktestParseResponse,
  RuleBacktestParsedStrategy,
  RuleBacktestRunRequest,
  RuleBacktestRunResponse,
} from '../../types/backtest';
import type { DeterministicBacktestNormalizedResult } from './normalizeDeterministicBacktestResult';
import { getAutoBenchmarkMode, getBenchmarkModeLabel, getStrategySpecValue } from './shared';
import { getRuleStrategyTypeLabel } from './strategyInspectability';

export type RuleScenarioPlanId =
  | 'benchmark_modes'
  | 'cost_stress'
  | 'lookback_window'
  | 'ma_window_variants'
  | 'macd_signal_variants'
  | 'rsi_threshold_variants';

export type RuleScenarioVariant = {
  id: string;
  label: string;
  description: string;
  request: RuleBacktestRunRequest;
};

export type RuleScenarioPlan = {
  id: RuleScenarioPlanId;
  label: string;
  description: string;
  variants: RuleScenarioVariant[];
};

export type RuleBacktestPreset = {
  id: string;
  kind: 'saved' | 'recent';
  name: string;
  savedAt: string;
  sourceRunId?: number | null;
  code: string;
  strategyText: string;
  startDate: string;
  endDate: string;
  lookbackBars: string;
  initialCapital: string;
  feeBps: string;
  slippageBps: string;
  benchmarkMode: string;
  benchmarkCode: string;
};

export type RuleRunNarrative = {
  verdict: string;
  headline: string;
  benchmarkLabel: string;
  drawdownLabel: string;
  activityLabel: string;
  qualityLabel: string;
  detail: string;
};

export const RULE_BACKTEST_PRESET_STORAGE_KEY = 'wolfystock.ruleBacktestPresets.v1';

const MAX_SAVED_PRESETS = 6;
const MAX_RECENT_PRESETS = 4;

function asFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function trimText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function pctLabel(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${value.toFixed(digits)}%`;
}

function moneyLabel(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return value.toFixed(2);
}

function dedupeVariants(variants: RuleScenarioVariant[]): RuleScenarioVariant[] {
  const seen = new Set<string>();
  return variants.filter((variant) => {
    const key = JSON.stringify({
      strategyText: variant.request.strategyText,
      lookbackBars: variant.request.lookbackBars,
      feeBps: variant.request.feeBps,
      slippageBps: variant.request.slippageBps,
      benchmarkMode: variant.request.benchmarkMode,
      benchmarkCode: variant.request.benchmarkCode,
      parsedStrategy: variant.request.parsedStrategy,
    });
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function getParsedStrategyFamily(run: Pick<RuleBacktestRunResponse, 'parsedStrategy'>): string {
  return trimText(String(
    getStrategySpecValue((run.parsedStrategy.strategySpec as Record<string, unknown> | undefined), ['strategy_type'])
      || run.parsedStrategy.strategyKind
      || run.parsedStrategy.detectedStrategyFamily
      || '',
  ));
}

function getRuleStrategySpec(parsedStrategy: RuleBacktestParsedStrategy | RuleBacktestParseResponse['parsedStrategy'] | null | undefined): Record<string, unknown> | undefined {
  if (!parsedStrategy) return undefined;
  if (parsedStrategy.strategySpec && typeof parsedStrategy.strategySpec === 'object') {
    return parsedStrategy.strategySpec as Record<string, unknown>;
  }
  if (parsedStrategy.setup && typeof parsedStrategy.setup === 'object') {
    return parsedStrategy.setup;
  }
  return undefined;
}

function getMaWindowSummary(spec: Record<string, unknown> | undefined): string | null {
  const fast = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'fast_period']));
  const slow = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'slow_period']));
  if (fast == null || slow == null) return null;
  const fastType = trimText(getStrategySpecValue(spec, ['signal', 'fast_type'])) || 'simple';
  const slowType = trimText(getStrategySpecValue(spec, ['signal', 'slow_type'])) || 'simple';
  const fastLabel = `${fastType === 'ema' ? 'EMA' : 'SMA'}${fast}`;
  const slowLabel = `${slowType === 'ema' ? 'EMA' : 'SMA'}${slow}`;
  return `${fastLabel}/${slowLabel}`;
}

function getMacdSummary(spec: Record<string, unknown> | undefined): string | null {
  const fast = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'fast_period']));
  const slow = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'slow_period']));
  const signal = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'signal_period']));
  if (fast == null || slow == null || signal == null) return null;
  return `MACD ${fast}/${slow}/${signal}`;
}

function getRsiSummary(spec: Record<string, unknown> | undefined): string | null {
  const period = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'period']));
  const lower = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'lower_threshold']));
  const upper = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'upper_threshold']));
  if (period == null || lower == null || upper == null) return null;
  return `RSI${period} ${lower}/${upper}`;
}

export function getRuleRunSetupHighlights(run: Pick<RuleBacktestRunResponse, 'code' | 'parsedStrategy' | 'lookbackBars' | 'feeBps' | 'slippageBps' | 'benchmarkMode' | 'benchmarkCode'>): string[] {
  const spec = getRuleStrategySpec(run.parsedStrategy);
  const family = getParsedStrategyFamily(run);
  const highlights: string[] = [];

  if (family === 'moving_average_crossover') {
    const summary = getMaWindowSummary(spec);
    if (summary) highlights.push(summary);
  } else if (family === 'macd_crossover') {
    const summary = getMacdSummary(spec);
    if (summary) highlights.push(summary);
  } else if (family === 'rsi_threshold') {
    const summary = getRsiSummary(spec);
    if (summary) highlights.push(summary);
  } else if (family === 'periodic_accumulation') {
    const frequency = trimText(String(getStrategySpecValue(spec, ['schedule', 'frequency']) || ''));
    const quantity = asFiniteNumber(getStrategySpecValue(spec, ['entry', 'order', 'quantity']));
    const amount = asFiniteNumber(getStrategySpecValue(spec, ['entry', 'order', 'amount']));
    if (frequency) highlights.push(`频率 ${frequency}`);
    if (quantity != null) highlights.push(`${quantity} 股/次`);
    if (amount != null) highlights.push(`${amount} 金额/次`);
  }

  highlights.push(`回看 ${run.lookbackBars} bars`);
  highlights.push(`费滑 ${Number(run.feeBps ?? 0).toFixed(1)}/${Number(run.slippageBps ?? 0).toFixed(1)}bp`);
  highlights.push(getBenchmarkModeLabel((run.benchmarkMode as Parameters<typeof getBenchmarkModeLabel>[0]) || 'auto', run.code, run.benchmarkCode || undefined));
  return highlights.slice(0, 4);
}

function getDrawdownLabel(value: number | null | undefined): string {
  const resolved = Math.abs(asFiniteNumber(value) ?? 0);
  if (resolved < 4) return '轻微回撤';
  if (resolved < 10) return '中等回撤';
  return '较深回撤';
}

function getTradeActivityLabel(tradeCount: number): string {
  if (tradeCount <= 2) return '低频';
  if (tradeCount <= 8) return '中频';
  return '高频';
}

function getQualityLabel(run: Pick<RuleBacktestRunResponse, 'winRatePct' | 'avgTradeReturnPct'>): string {
  const winRate = asFiniteNumber(run.winRatePct);
  const avgTradeReturn = asFiniteNumber(run.avgTradeReturnPct);
  if (winRate != null && avgTradeReturn != null) {
    if (winRate >= 60 && avgTradeReturn >= 1) return '信号质量较稳';
    if (winRate < 45 || avgTradeReturn < 0) return '信号质量偏弱';
  }
  if (winRate != null) {
    if (winRate >= 60) return '胜率较稳';
    if (winRate < 45) return '胜率偏弱';
  }
  return '质量待结合更多样本观察';
}

export function describeRuleRunNarrative(run: Pick<RuleBacktestRunResponse, 'benchmarkMode' | 'benchmarkCode' | 'benchmarkReturnPct' | 'buyAndHoldReturnPct' | 'excessReturnVsBenchmarkPct' | 'excessReturnVsBuyAndHoldPct' | 'maxDrawdownPct' | 'tradeCount' | 'winRatePct' | 'avgTradeReturnPct' | 'code'>): RuleRunNarrative {
  const benchmarkMode = (run.benchmarkMode as Parameters<typeof getBenchmarkModeLabel>[0]) || 'auto';
  const benchmarkLabel = getBenchmarkModeLabel(benchmarkMode, run.code, run.benchmarkCode || undefined);
  const benchmarkDelta = asFiniteNumber(run.excessReturnVsBenchmarkPct);
  const buyHoldDelta = asFiniteNumber(run.excessReturnVsBuyAndHoldPct);
  const relativeDelta = benchmarkDelta ?? buyHoldDelta;
  const relativeTarget = benchmarkDelta != null ? benchmarkLabel : '买入持有';
  let verdict = '接近基准';
  if (relativeDelta != null) {
    if (relativeDelta >= 1) verdict = `跑赢 ${relativeTarget}`;
    else if (relativeDelta <= -1) verdict = `落后于 ${relativeTarget}`;
  }

  const drawdownLabel = getDrawdownLabel(run.maxDrawdownPct);
  const activityLabel = getTradeActivityLabel(Number(run.tradeCount ?? 0));
  const qualityLabel = getQualityLabel(run);
  const deltaLabel = relativeDelta == null ? '暂无可比较基准' : `${verdict} ${pctLabel(relativeDelta)}`;

  return {
    verdict,
    headline: `${deltaLabel}，${drawdownLabel}，${activityLabel}交易节奏。`,
    benchmarkLabel,
    drawdownLabel,
    activityLabel,
    qualityLabel,
    detail: [
      `相对表现：${deltaLabel}`,
      `风险：${drawdownLabel}（最大回撤 ${pctLabel(run.maxDrawdownPct)}）`,
      `活跃度：${activityLabel}（交易 ${run.tradeCount || 0} 次）`,
      `质量：${qualityLabel}`,
    ].join(' '),
  };
}

export function getRuleRunExecutionNotes(run: Pick<RuleBacktestRunResponse, 'executionTrace' | 'benchmarkSummary' | 'noResultMessage' | 'parsedStrategy' | 'warnings'>): string[] {
  const notes = [
    trimText(run.executionTrace?.fallback?.note),
    trimText(run.executionTrace?.assumptionsDefaults?.summaryText),
    trimText(run.benchmarkSummary?.unavailableReason),
    trimText(run.noResultMessage),
    ...((run.parsedStrategy.parseWarnings || []).map((item) => trimText(item.message || item.reason || item.code))),
    ...((run.warnings || []).map((item) => trimText(item.message || item.reason || item.code))),
  ].filter(Boolean);

  return Array.from(new Set(notes)).slice(0, 4);
}

export function buildRuleRunComparisonWarnings(runs: Array<Pick<RuleBacktestRunResponse, 'startDate' | 'endDate' | 'lookbackBars' | 'feeBps' | 'slippageBps' | 'benchmarkMode' | 'benchmarkCode' | 'code' | 'parsedStrategy'>>): string[] {
  if (runs.length <= 1) return [];
  const warnings: string[] = [];
  const signatures = {
    dateRange: new Set(runs.map((run) => `${run.startDate || '--'}:${run.endDate || '--'}`)),
    costs: new Set(runs.map((run) => `${Number(run.feeBps ?? 0).toFixed(2)}:${Number(run.slippageBps ?? 0).toFixed(2)}`)),
    benchmark: new Set(runs.map((run) => `${run.benchmarkMode || 'auto'}:${run.benchmarkCode || ''}`)),
    lookback: new Set(runs.map((run) => String(run.lookbackBars || '--'))),
    family: new Set(runs.map((run) => getParsedStrategyFamily(run))),
  };

  if (signatures.dateRange.size > 1) warnings.push('比较项使用了不同日期区间，收益与回撤不完全可直接横比。');
  if (signatures.costs.size > 1) warnings.push('比较项的手续费或滑点假设不同，净收益差异会放大。');
  if (signatures.benchmark.size > 1) warnings.push('比较项使用了不同基准设置，超额收益只适合在相同基准下直接对照。');
  if (signatures.lookback.size > 1) warnings.push('比较项的 lookback 初始化窗口不同，技术信号 warmup 结果可能不同。');
  if (signatures.family.size > 1) warnings.push('比较项跨了不同策略族，更适合看风格差异而不是只看单一胜负。');
  return warnings;
}

export function buildRuleRunReportMarkdown(args: {
  run: RuleBacktestRunResponse;
  normalized: DeterministicBacktestNormalizedResult;
  comparedRuns?: RuleBacktestRunResponse[];
}): string {
  const { run, normalized, comparedRuns = [] } = args;
  const narrative = describeRuleRunNarrative(run);
  const setupHighlights = getRuleRunSetupHighlights(run);
  const executionNotes = getRuleRunExecutionNotes(run);
  const comparisonWarnings = buildRuleRunComparisonWarnings([run, ...comparedRuns]);
  const comparedSummary = comparedRuns.length > 0
    ? comparedRuns.map((item) => {
      const label = `#${item.id} · ${getRuleStrategyTypeLabel(item.parsedStrategy)} · ${pctLabel(item.totalReturnPct)}`;
      return `- ${label} · 超额 ${pctLabel(item.excessReturnVsBenchmarkPct ?? item.excessReturnVsBuyAndHoldPct)} · 回撤 ${pctLabel(item.maxDrawdownPct)}`;
    }).join('\n')
    : '- 暂未附加其他比较对象';

  return [
    `# 确定性回测决策摘要 #${run.id}`,
    '',
    `- 标的：${run.code}`,
    `- 策略：${getRuleStrategyTypeLabel(run.parsedStrategy)}`,
    `- 区间：${run.startDate || '--'} -> ${run.endDate || '--'}`,
    `- 基准：${run.benchmarkSummary?.label || narrative.benchmarkLabel}`,
    `- 结论：${narrative.headline}`,
    '',
    '## 决策摘要',
    '',
    `- 总收益：${pctLabel(normalized.metrics.totalReturnPct)}`,
    `- 相对基准：${pctLabel(normalized.metrics.excessReturnVsBenchmarkPct ?? normalized.metrics.excessReturnVsBuyAndHoldPct)}`,
    `- 最大回撤：${pctLabel(normalized.metrics.maxDrawdownPct)}（${narrative.drawdownLabel}）`,
    `- 交易次数：${normalized.metrics.tradeCount}（${narrative.activityLabel}）`,
    `- 胜率：${pctLabel(normalized.metrics.winRatePct)}`,
    `- 期末权益：${moneyLabel(normalized.metrics.finalEquity)}`,
    '',
    '## 关键配置',
    '',
    ...setupHighlights.map((item) => `- ${item}`),
    '',
    '## 执行与解释',
    '',
    ...(executionNotes.length > 0 ? executionNotes.map((item) => `- ${item}`) : ['- 暂无额外执行备注']),
    '',
    '## 对比参考',
    '',
    comparedSummary,
    '',
    ...(comparisonWarnings.length > 0
      ? [
        '## 比较提醒',
        '',
        ...comparisonWarnings.map((item) => `- ${item}`),
        '',
      ]
      : []),
    '## 深层数据',
    '',
    '- 详细执行轨迹仍以 CSV / JSON 导出为准。',
    '- 图表解读优先查看收益曲线、回撤曲线和基准对照。',
  ].join('\n');
}

export function createRuleBacktestPresetFromRun(
  run: Pick<RuleBacktestRunResponse, 'id' | 'code' | 'strategyText' | 'startDate' | 'endDate' | 'lookbackBars' | 'initialCapital' | 'feeBps' | 'slippageBps' | 'benchmarkMode' | 'benchmarkCode' | 'parsedStrategy'>,
  options?: { kind?: 'saved' | 'recent'; name?: string },
): RuleBacktestPreset {
  const kind = options?.kind || 'saved';
  const familyLabel = getRuleStrategyTypeLabel(run.parsedStrategy);
  return {
    id: `${kind}-${run.id ?? 'draft'}-${Date.now()}`,
    kind,
    name: trimText(options?.name) || `${run.code} · ${familyLabel}`,
    savedAt: new Date().toISOString(),
    sourceRunId: run.id ?? null,
    code: run.code,
    strategyText: run.strategyText,
    startDate: run.startDate || '',
    endDate: run.endDate || '',
    lookbackBars: String(run.lookbackBars ?? 252),
    initialCapital: String(run.initialCapital ?? 100000),
    feeBps: String(run.feeBps ?? 0),
    slippageBps: String(run.slippageBps ?? 0),
    benchmarkMode: run.benchmarkMode || 'auto',
    benchmarkCode: run.benchmarkCode || '',
  };
}

export function loadRuleBacktestPresets(): RuleBacktestPreset[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(RULE_BACKTEST_PRESET_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item): item is RuleBacktestPreset => Boolean(item && typeof item === 'object' && item.id))
      .sort((left, right) => String(right.savedAt || '').localeCompare(String(left.savedAt || '')));
  } catch {
    return [];
  }
}

function persistRuleBacktestPresets(items: RuleBacktestPreset[]): RuleBacktestPreset[] {
  const saved = items.filter((item) => item.kind === 'saved').slice(0, MAX_SAVED_PRESETS);
  const recent = items.filter((item) => item.kind === 'recent').slice(0, MAX_RECENT_PRESETS);
  const next = [...saved, ...recent].sort((left, right) => String(right.savedAt || '').localeCompare(String(left.savedAt || '')));
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(RULE_BACKTEST_PRESET_STORAGE_KEY, JSON.stringify(next));
  }
  return next;
}

export function saveRuleBacktestPreset(preset: RuleBacktestPreset): RuleBacktestPreset[] {
  const existing = loadRuleBacktestPresets();
  const filtered = existing.filter((item) => item.id !== preset.id);
  if (preset.kind === 'recent') {
    const signature = `${preset.code}:${preset.strategyText}:${preset.startDate}:${preset.endDate}:${preset.lookbackBars}:${preset.initialCapital}:${preset.feeBps}:${preset.slippageBps}:${preset.benchmarkMode}:${preset.benchmarkCode}`;
    const deduped = filtered.filter((item) => {
      if (item.kind !== 'recent') return true;
      const itemSignature = `${item.code}:${item.strategyText}:${item.startDate}:${item.endDate}:${item.lookbackBars}:${item.initialCapital}:${item.feeBps}:${item.slippageBps}:${item.benchmarkMode}:${item.benchmarkCode}`;
      return itemSignature !== signature;
    });
    return persistRuleBacktestPresets([preset, ...deduped]);
  }
  return persistRuleBacktestPresets([preset, ...filtered]);
}

export function deleteRuleBacktestPreset(presetId: string): RuleBacktestPreset[] {
  const existing = loadRuleBacktestPresets();
  return persistRuleBacktestPresets(existing.filter((item) => item.id !== presetId));
}

function createScenarioRequest(
  run: RuleBacktestRunResponse,
  label: string,
  overrides: Partial<RuleBacktestRunRequest>,
  parsedStrategyOverride?: RuleBacktestRunRequest['parsedStrategy'],
): RuleScenarioVariant {
  const strategyText = trimText(overrides.strategyText) || `${run.strategyText}\n[P6 variant] ${label}`;
  return {
    id: label.toLowerCase().replace(/\s+/g, '-'),
    label,
    description: trimText(overrides.strategyText) || label,
    request: {
      code: run.code,
      strategyText,
      parsedStrategy: parsedStrategyOverride ?? cloneJson(run.parsedStrategy),
      startDate: run.startDate || undefined,
      endDate: run.endDate || undefined,
      lookbackBars: overrides.lookbackBars ?? run.lookbackBars,
      initialCapital: overrides.initialCapital ?? run.initialCapital,
      feeBps: overrides.feeBps ?? run.feeBps,
      slippageBps: overrides.slippageBps ?? run.slippageBps,
      benchmarkMode: overrides.benchmarkMode ?? run.benchmarkMode ?? 'auto',
      benchmarkCode: overrides.benchmarkCode ?? run.benchmarkCode ?? undefined,
      confirmed: true,
      waitForCompletion: false,
    },
  };
}

function withUpdatedParsedStrategy(
  run: RuleBacktestRunResponse,
  updater: (spec: Record<string, unknown>) => void,
  textSuffix: string,
): RuleScenarioVariant | null {
  const parsedStrategy = cloneJson(run.parsedStrategy);
  const spec = getRuleStrategySpec(parsedStrategy);
  if (!spec) return null;
  updater(spec);
  parsedStrategy.strategySpec = spec;
  return createScenarioRequest(run, textSuffix, {
    strategyText: `${run.strategyText}\n[P6 variant] ${textSuffix}`,
  }, parsedStrategy);
}

export function getRuleScenarioPlans(run: RuleBacktestRunResponse): RuleScenarioPlan[] {
  const plans: RuleScenarioPlan[] = [];
  const autoBenchmarkMode = getAutoBenchmarkMode(run.code);
  const benchmarkVariants = dedupeVariants([
    createScenarioRequest(run, 'Auto Benchmark', { benchmarkMode: 'auto', benchmarkCode: undefined }),
    createScenarioRequest(run, 'No Benchmark', { benchmarkMode: 'none', benchmarkCode: undefined }),
    createScenarioRequest(run, 'Buy and Hold Benchmark', { benchmarkMode: 'same_symbol_buy_and_hold', benchmarkCode: undefined }),
    createScenarioRequest(run, 'Market Benchmark', {
      benchmarkMode: autoBenchmarkMode,
      benchmarkCode: undefined,
    }),
  ]).filter((item) => item.request.benchmarkMode !== run.benchmarkMode || (item.request.benchmarkCode || '') !== (run.benchmarkCode || ''));

  if (benchmarkVariants.length > 0) {
    plans.push({
      id: 'benchmark_modes',
      label: '基准情景',
      description: '快速比较当前策略在不同 benchmark context 下的超额表现。',
      variants: benchmarkVariants.slice(0, 3),
    });
  }

  plans.push({
    id: 'cost_stress',
    label: '费用/滑点压力',
    description: '对同一策略做轻量摩擦压力测试，观察净收益对成本的敏感度。',
    variants: dedupeVariants([
      createScenarioRequest(run, 'Base Cost', {}),
      createScenarioRequest(run, 'Cost +5bp', {
        feeBps: Number(run.feeBps ?? 0) + 5,
        slippageBps: Number(run.slippageBps ?? 0) + 5,
      }),
      createScenarioRequest(run, 'Cost +10bp', {
        feeBps: Number(run.feeBps ?? 0) + 10,
        slippageBps: Number(run.slippageBps ?? 0) + 10,
      }),
    ]).filter((item) => !(item.request.feeBps === run.feeBps && item.request.slippageBps === run.slippageBps)).slice(0, 2),
  });

  plans.push({
    id: 'lookback_window',
    label: 'Lookback 窗口',
    description: '用更短/更长 warmup 窗口验证策略初始化对结果的影响。',
    variants: dedupeVariants([
      createScenarioRequest(run, 'Lookback 126', { lookbackBars: Math.max(63, Math.min(126, run.lookbackBars)) }),
      createScenarioRequest(run, `Lookback ${run.lookbackBars + 126}`, { lookbackBars: run.lookbackBars + 126 }),
    ]).filter((item) => item.request.lookbackBars !== run.lookbackBars).slice(0, 2),
  });

  const family = getParsedStrategyFamily(run);
  if (family === 'moving_average_crossover') {
    const maFastVariant = withUpdatedParsedStrategy(run, (spec) => {
      const currentFast = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'fast_period'])) ?? 5;
      const currentSlow = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'slow_period'])) ?? 20;
      const nextFast = Math.max(2, currentFast - 2);
      const nextSlow = Math.max(nextFast + 3, currentSlow - 5);
      if (spec.signal && typeof spec.signal === 'object') {
        (spec.signal as Record<string, unknown>).fast_period = nextFast;
        (spec.signal as Record<string, unknown>).slow_period = nextSlow;
      }
    }, 'MA Faster');
    const maSlowVariant = withUpdatedParsedStrategy(run, (spec) => {
      const currentFast = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'fast_period'])) ?? 5;
      const currentSlow = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'slow_period'])) ?? 20;
      if (spec.signal && typeof spec.signal === 'object') {
        (spec.signal as Record<string, unknown>).fast_period = currentFast + 2;
        (spec.signal as Record<string, unknown>).slow_period = currentSlow + 5;
      }
    }, 'MA Slower');
    const variants = [maFastVariant, maSlowVariant].filter((item): item is RuleScenarioVariant => Boolean(item));
    if (variants.length > 0) {
      plans.push({
        id: 'ma_window_variants',
        label: '均线窗口变体',
        description: '围绕当前 fast/slow window 生成两组轻量 MA 变体，便于快速做 first-step iteration。',
        variants: dedupeVariants(variants),
      });
    }
  } else if (family === 'macd_crossover') {
    const fastVariant = withUpdatedParsedStrategy(run, (spec) => {
      if (spec.signal && typeof spec.signal === 'object') {
        const signal = spec.signal as Record<string, unknown>;
        signal.fast_period = 8;
        signal.slow_period = 21;
        signal.signal_period = 5;
      }
    }, 'MACD Fast');
    const slowVariant = withUpdatedParsedStrategy(run, (spec) => {
      if (spec.signal && typeof spec.signal === 'object') {
        const signal = spec.signal as Record<string, unknown>;
        signal.fast_period = 15;
        signal.slow_period = 30;
        signal.signal_period = 9;
      }
    }, 'MACD Slow');
    const variants = [fastVariant, slowVariant].filter((item): item is RuleScenarioVariant => Boolean(item));
    if (variants.length > 0) {
      plans.push({
        id: 'macd_signal_variants',
        label: 'MACD 参数变体',
        description: '固定策略结构，只比较更快/更慢的一组 MACD 周期组合。',
        variants: dedupeVariants(variants),
      });
    }
  } else if (family === 'rsi_threshold') {
    const aggressiveVariant = withUpdatedParsedStrategy(run, (spec) => {
      if (spec.signal && typeof spec.signal === 'object') {
        const signal = spec.signal as Record<string, unknown>;
        signal.period = 10;
        signal.lower_threshold = 35;
        signal.upper_threshold = 65;
      }
    }, 'RSI Aggressive');
    const patientVariant = withUpdatedParsedStrategy(run, (spec) => {
      if (spec.signal && typeof spec.signal === 'object') {
        const signal = spec.signal as Record<string, unknown>;
        signal.period = 18;
        signal.lower_threshold = 25;
        signal.upper_threshold = 75;
      }
    }, 'RSI Patient');
    const variants = [aggressiveVariant, patientVariant].filter((item): item is RuleScenarioVariant => Boolean(item));
    if (variants.length > 0) {
      plans.push({
        id: 'rsi_threshold_variants',
        label: 'RSI 阈值变体',
        description: '比较更激进与更耐心的 RSI 触发区间。',
        variants: dedupeVariants(variants),
      });
    }
  }

  return plans.filter((plan) => plan.variants.length > 0);
}
