const HAN_RE = /[\u3400-\u9fff]/;

type StrategyText = {
  name: string;
  description?: string;
  category?: string;
};

const STRATEGY_TEXT: Record<string, StrategyText> = {
  bull_trend: {
    name: 'Bull Trend',
    description: 'Trend-following setup for stocks with improving price structure and momentum.',
    category: 'Trend',
  },
  ma_golden_cross: {
    name: 'Moving Average Golden Cross',
    description: 'Looks for bullish moving-average alignment and improving follow-through.',
    category: 'Trend',
  },
  chan_theory: {
    name: 'Chan Theory',
    description: 'Structure-based analysis using Chan-style strokes, pivots, and trend changes.',
    category: 'Structure',
  },
  wave_theory: {
    name: 'Elliott Wave',
    description: 'Reviews likely wave structure, trend phase, and invalidation levels.',
    category: 'Structure',
  },
  box_oscillation: {
    name: 'Range Trading',
    description: 'Assesses range-bound setups, support, resistance, and breakout risk.',
    category: 'Mean Reversion',
  },
  emotion_cycle: {
    name: 'Sentiment Cycle',
    description: 'Reviews market sentiment, crowding, and likely cycle phase.',
    category: 'Sentiment',
  },
  growth_quality: {
    name: 'Growth Quality',
    description: 'Screens for quality growth signals, earnings durability, and valuation discipline.',
    category: 'Quality',
  },
  default: {
    name: 'Default Strategy',
    description: 'Balanced stock analysis using the default configured strategy set.',
    category: 'Default',
  },
  dual_low: {
    name: 'Dual Low',
    description: 'Value-oriented screen for low valuation and lower downside risk.',
    category: 'Value',
  },
  balanced_alpha: {
    name: 'Balanced Alpha',
    description: 'Balanced multi-factor screen for quality, value, and momentum.',
    category: 'Framework',
  },
  capital_heat: {
    name: 'Capital Heat',
    description: 'Momentum screen focused on turnover, liquidity, and capital-flow pressure.',
    category: 'Momentum',
  },
  oversold_reversal: {
    name: 'Oversold Reversal',
    description: 'Looks for stretched downside moves where reversal risk is improving.',
    category: 'Reversal',
  },
  shrink_pullback: {
    name: 'Low-Volume Pullback',
    description: 'Trend pullback screen for constructive consolidation on lighter volume.',
    category: 'Trend',
  },
};

const PHRASE_TRANSLATIONS: Array<[RegExp, string]> = [
  [/默认策略/g, 'Default Strategy'],
  [/默认多头趋势/g, 'Default Bull Trend'],
  [/多头趋势/g, 'Bull Trend'],
  [/趋势分析/g, 'Trend Analysis'],
  [/均线金叉/g, 'Moving Average Golden Cross'],
  [/缠论/g, 'Chan Theory'],
  [/波浪理论/g, 'Elliott Wave'],
  [/箱体震荡/g, 'Range Trading'],
  [/情绪周期/g, 'Sentiment Cycle'],
  [/成长质量/g, 'Growth Quality'],
  [/通用分析/g, 'General Analysis'],
  [/通用/g, 'General'],
  [/自定义策略/g, 'Custom Strategy'],
  [/自定义/g, 'Custom'],
  [/平衡选股/g, 'Balanced Alpha'],
  [/资金热度/g, 'Capital Heat'],
  [/双低选股/g, 'Dual Low'],
  [/双低/g, 'Dual Low'],
  [/超跌/g, 'Oversold Reversal'],
  [/缩量回踩/g, 'Low-Volume Pullback'],
  [/价值/g, 'Value'],
  [/动量/g, 'Momentum'],
  [/反转/g, 'Reversal'],
  [/趋势/g, 'Trend'],
  [/框架/g, 'Framework'],
  [/观察/g, 'Watch'],
  [/买入/g, 'Buy'],
  [/卖出/g, 'Sell'],
  [/持有/g, 'Hold'],
  [/行情/g, 'Quote'],
  [/新闻/g, 'News'],
  [/基本面/g, 'Fundamentals'],
  [/技术/g, 'Technical'],
  [/筹码/g, 'Positioning'],
  [/正常/g, 'Normal'],
  [/部分降级/g, 'Partially degraded'],
  [/降级/g, 'Degraded'],
  [/失败/g, 'Failed'],
  [/未知/g, 'Unknown'],
  [/未配置/g, 'Not configured'],
  [/已跳过/g, 'Skipped'],
  [/可用/g, 'Available'],
  [/缺失/g, 'Missing'],
  [/不支持/g, 'Unsupported'],
  [/过期/g, 'Stale'],
  [/估算/g, 'Estimated'],
  [/部分/g, 'Partial'],
  [/抓取失败/g, 'Fetch failed'],
  [/良好/g, 'Good'],
  [/受限/g, 'Limited'],
  [/较差/g, 'Poor'],
];

export function hasChineseText(value: unknown): boolean {
  return typeof value === 'string' && HAN_RE.test(value);
}

export function formatIdentifier(value: string): string {
  const cleaned = value.trim().replace(/[_-]+/g, ' ');
  if (!cleaned) {
    return 'Unknown';
  }

  return cleaned.replace(/\b\w/g, (character) => character.toUpperCase());
}

export function toEnglishText(value: unknown, fallback = ''): string {
  if (value == null) {
    return fallback;
  }

  let text = String(value).trim();
  if (!text) {
    return fallback;
  }

  for (const [pattern, replacement] of PHRASE_TRANSLATIONS) {
    text = text.replace(pattern, replacement);
  }

  return HAN_RE.test(text) ? fallback || 'Unavailable' : text;
}

export function getEnglishStrategyText(
  strategyId: string | undefined,
  rawName?: unknown,
  rawDescription?: unknown,
  rawCategory?: unknown,
): StrategyText {
  const mapped = strategyId ? STRATEGY_TEXT[strategyId] : undefined;
  const fallbackName = strategyId ? formatIdentifier(strategyId) : 'Strategy';
  return {
    name: mapped?.name || toEnglishText(rawName, fallbackName),
    description: mapped?.description || toEnglishText(rawDescription, strategyId ? `Uses the ${fallbackName} strategy.` : 'Balanced strategy analysis.'),
    category: mapped?.category || toEnglishText(rawCategory, strategyId ? formatIdentifier(strategyId) : 'Strategy'),
  };
}

export function joinEnglishList(values: Array<unknown>, fallback = 'None'): string {
  const cleaned = values
    .map((value) => toEnglishText(value, ''))
    .filter(Boolean);

  return cleaned.length ? cleaned.join(', ') : fallback;
}
