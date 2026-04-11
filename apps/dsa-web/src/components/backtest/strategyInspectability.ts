import type { RuleBacktestParsedStrategy } from '../../types/backtest';
import {
  formatCashPolicy,
  formatDraftOrder,
  formatExecutionPriceBasis,
  formatExitPolicy,
  formatNumber,
  getPeriodicNumber,
  getPeriodicString,
  getStrategySpecValue,
} from './shared';

export type RuleStrategySummaryRow = {
  key: string;
  label: string;
  value: string;
};

export function formatRuleStrategyFamily(strategyType: string): string {
  if (strategyType === 'periodic_accumulation') return '区间定投';
  if (strategyType === 'moving_average_crossover') return '均线交叉';
  if (strategyType === 'macd_crossover') return 'MACD 交叉';
  if (strategyType === 'rsi_threshold') return 'RSI 阈值';
  if (strategyType === 'rule_conditions') return '条件规则';
  return strategyType || '--';
}

export function getRuleStrategyTypeLabel(
  parsedStrategy: Pick<RuleBacktestParsedStrategy, 'strategyKind' | 'detectedStrategyFamily' | 'strategySpec' | 'setup'> | null | undefined,
  topLevelDetectedStrategyFamily?: string | null,
): string {
  const spec = parsedStrategy?.strategySpec && typeof parsedStrategy.strategySpec === 'object'
    ? parsedStrategy.strategySpec
    : parsedStrategy?.setup && typeof parsedStrategy.setup === 'object'
      ? parsedStrategy.setup
      : undefined;
  const normalizedStrategyType = String(getStrategySpecValue(spec, ['strategy_type']) || '');
  const parsedStrategyKind = String(parsedStrategy?.strategyKind || '');
  const detectedStrategyFamily = String(topLevelDetectedStrategyFamily || parsedStrategy?.detectedStrategyFamily || '') || '';
  const strategyType = normalizedStrategyType
    || (parsedStrategyKind && parsedStrategyKind !== 'rule_conditions' ? parsedStrategyKind : '')
    || detectedStrategyFamily
    || parsedStrategyKind;
  return formatRuleStrategyFamily(strategyType);
}

export function getRuleStrategySpecSourceLabel(
  parsedStrategy: Pick<RuleBacktestParsedStrategy, 'strategySpec' | 'setup'> | null | undefined,
): string {
  if (!parsedStrategy) return '未结构化';
  const direct = parsedStrategy.strategySpec;
  if (direct && typeof direct === 'object') return '显式 strategy_spec';
  const fallback = parsedStrategy.setup;
  if (fallback && typeof fallback === 'object') return '兼容 setup';
  return '未结构化';
}

export function formatRuleNormalizationStateLabel(state?: string | null): string {
  if (state === 'ready') return '已完成归一化';
  if (state === 'assumed') return '含默认补全';
  if (state === 'unsupported') return '当前不支持';
  if (state === 'pending') return '待解析';
  return state || '--';
}

function formatFrequencyLabel(spec: Record<string, unknown> | undefined, strategyKind?: string | null): string {
  const strategyType = String(getStrategySpecValue(spec, ['strategy_type']) || strategyKind || '');
  if (strategyType === 'periodic_accumulation') {
    const frequency = getPeriodicString(spec, 'execution_frequency');
    if (frequency === 'daily') return '每个交易日';
    if (frequency === 'weekly') return '每周';
    if (frequency === 'monthly') return '每月';
    return frequency === '--' ? '--' : frequency;
  }
  return '按日线信号';
}

function formatStrategyCondition(
  spec: Record<string, unknown> | undefined,
  parsedStrategy: Pick<RuleBacktestParsedStrategy, 'strategyKind' | 'summary'> | null | undefined,
  side: 'entry' | 'exit',
): string {
  const strategyType = String(getStrategySpecValue(spec, ['strategy_type']) || parsedStrategy?.strategyKind || '');
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
  return side === 'entry' ? parsedStrategy?.summary?.entry || '--' : parsedStrategy?.summary?.exit || '--';
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

export function buildRuleStrategySummaryRows(
  parsedStrategy: Pick<RuleBacktestParsedStrategy, 'strategyKind' | 'detectedStrategyFamily' | 'strategySpec' | 'setup' | 'summary'> | null | undefined,
  currentCode: string,
  startDate: string,
  endDate: string,
  topLevelDetectedStrategyFamily?: string | null,
): RuleStrategySummaryRow[] {
  if (!parsedStrategy) return [];

  const spec = parsedStrategy.strategySpec && typeof parsedStrategy.strategySpec === 'object'
    ? parsedStrategy.strategySpec
    : parsedStrategy.setup && typeof parsedStrategy.setup === 'object'
      ? parsedStrategy.setup
      : undefined;
  const strategyType = String(getStrategySpecValue(spec, ['strategy_type']) || parsedStrategy.strategyKind || '');

  if (strategyType === 'periodic_accumulation') {
    return [
      { key: 'strategy_family', label: '策略族', value: getRuleStrategyTypeLabel(parsedStrategy, topLevelDetectedStrategyFamily) },
      { key: 'symbol', label: '标的', value: getPeriodicString(spec, 'symbol') || currentCode || '--' },
      { key: 'date_range', label: '日期区间', value: `${getPeriodicString(spec, 'start_date') || startDate || '--'} -> ${getPeriodicString(spec, 'end_date') || endDate || '--'}` },
      { key: 'initial_capital', label: '初始资金', value: formatNumber(getPeriodicNumber(spec, 'initial_capital')) },
      { key: 'frequency', label: '执行频率', value: formatFrequencyLabel(spec, parsedStrategy.strategyKind) },
      { key: 'entry', label: '买入条件', value: formatDraftOrder(spec) },
      { key: 'fill_timing', label: '成交时点', value: formatExecutionPriceBasis(spec) },
      { key: 'exit', label: '卖出条件', value: formatExitPolicy(spec) },
      { key: 'cash_policy', label: '现金策略', value: formatCashPolicy(spec) },
      { key: 'costs', label: '交易成本', value: `手续费 ${formatNumber(getPeriodicNumber(spec, 'fee_bps'), 0)} bp / 滑点 ${formatNumber(getPeriodicNumber(spec, 'slippage_bps'), 0)} bp` },
    ];
  }

  if (strategyType === 'moving_average_crossover' || strategyType === 'macd_crossover' || strategyType === 'rsi_threshold') {
    return [
      { key: 'strategy_family', label: '策略族', value: getRuleStrategyTypeLabel(parsedStrategy, topLevelDetectedStrategyFamily) },
      { key: 'symbol', label: '标的', value: String(getStrategySpecValue(spec, ['symbol']) || currentCode || '--') },
      { key: 'date_range', label: '日期区间', value: `${String(getStrategySpecValue(spec, ['date_range', 'start_date']) || startDate || '--')} -> ${String(getStrategySpecValue(spec, ['date_range', 'end_date']) || endDate || '--')}` },
      { key: 'initial_capital', label: '初始资金', value: formatNumber(Number(getStrategySpecValue(spec, ['capital', 'initial_capital']) || 0)) },
      { key: 'entry', label: '买入条件', value: formatStrategyCondition(spec, parsedStrategy, 'entry') },
      { key: 'exit', label: '卖出条件', value: formatStrategyCondition(spec, parsedStrategy, 'exit') },
      { key: 'frequency', label: '执行频率', value: formatExecutionFrequency(spec) },
      { key: 'signal_timing', label: '信号时点', value: formatExecutionTimingValue(getStrategySpecValue(spec, ['execution', 'signal_timing'])) },
      { key: 'fill_timing', label: '成交时点', value: formatExecutionTimingValue(getStrategySpecValue(spec, ['execution', 'fill_timing'])) },
      { key: 'end_behavior', label: '期末处理', value: formatEndBehavior(spec) },
      { key: 'costs', label: '交易成本', value: `手续费 ${formatNumber(Number(getStrategySpecValue(spec, ['costs', 'fee_bps']) || 0), 0)} bp / 滑点 ${formatNumber(Number(getStrategySpecValue(spec, ['costs', 'slippage_bps']) || 0), 0)} bp` },
    ];
  }

  return [
    { key: 'strategy_family', label: '策略族', value: getRuleStrategyTypeLabel(parsedStrategy, topLevelDetectedStrategyFamily) },
    { key: 'symbol', label: '标的', value: currentCode || '--' },
    { key: 'entry', label: '买入条件', value: parsedStrategy.summary?.entry || '--' },
    { key: 'exit', label: '卖出条件', value: parsedStrategy.summary?.exit || '--' },
    { key: 'date_range', label: '日期区间', value: `${startDate || '--'} -> ${endDate || '--'}` },
  ];
}
