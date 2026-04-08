export type MarketColorConvention = 'redDownGreenUp' | 'redUpGreenDown';

export const MARKET_COLOR_CONVENTION_STORAGE_KEY = 'dsa-market-color-convention';
export const DEFAULT_MARKET_COLOR_CONVENTION: MarketColorConvention = 'redDownGreenUp';

export function normalizeMarketColorConvention(
  value?: string | null,
): MarketColorConvention {
  if (value === 'redDownGreenUp' || value === 'redUpGreenDown') {
    return value;
  }
  return DEFAULT_MARKET_COLOR_CONVENTION;
}

export function getMarketColorPalette(convention: MarketColorConvention): {
  upHsl: string;
  downHsl: string;
} {
  if (convention === 'redUpGreenDown') {
    return {
      upHsl: '4 82% 62%',
      downHsl: '145 66% 52%',
    };
  }

  return {
    upHsl: '145 66% 52%',
    downHsl: '4 82% 62%',
  };
}

export function getMarketDirectionColor(value?: number | null): string | undefined {
  if (value == null || !Number.isFinite(value) || value === 0) {
    return undefined;
  }
  return value > 0 ? 'var(--market-up)' : 'var(--market-down)';
}
