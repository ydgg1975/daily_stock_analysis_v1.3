/**
 * SuggestionsList Component
 *
 * Stock search suggestion list
 * Displays matched stock options
 */

import type { CSSProperties } from 'react';
import type { StockSuggestion } from '../../types/stockIndex';
import { cn } from '../../utils/cn';

export interface SuggestionsListProps {
  /** Suggestion list */
  suggestions: StockSuggestion[];
  /** Highlighted index */
  highlightedIndex: number;
  /** Selection callback */
  onSelect: (suggestion: StockSuggestion) => void;
  /** Mouse hover callback */
  onMouseEnter: (index: number) => void;
  /** Custom style (for Portal fixed positioning) */
  style?: CSSProperties;
}

export function SuggestionsList({
  suggestions,
  highlightedIndex,
  onSelect,
  onMouseEnter,
  style,
}: SuggestionsListProps) {
  if (suggestions.length === 0) {
    return null;
  }

  return (
    <ul
      id="suggestions-list"
      className="theme-dropdown-panel z-[100] max-h-60 overflow-auto rounded-b-lg rounded-t-none border-x border-b"
      style={style}
      role="listbox"
    >
      {suggestions.map((suggestion, index) => (
        <li
          key={suggestion.canonicalCode}
          role="option"
          aria-selected={index === highlightedIndex}
          data-active={index === highlightedIndex ? 'true' : 'false'}
          className={cn(
            "theme-dropdown-item px-4 py-1 cursor-pointer flex items-center justify-between"
          )}
          onClick={() => onSelect(suggestion)}
          onMouseEnter={() => onMouseEnter(index)}
        >
          <div className="flex items-center gap-3">
            {/* Market badge */}
            <MarketBadge market={suggestion.market} />

            {/* Name and code */}
            <div className="flex flex-col">
              <span className="text-sm font-medium text-foreground">
                {suggestion.nameZh}
              </span>
              <span className="text-sm text-secondary-text">
                {suggestion.displayCode}
              </span>
            </div>
          </div>

          {/* Match type badge */}
          <MatchTypeBadge matchType={suggestion.matchType} />
        </li>
      ))}
    </ul>
  );
}

// Helper component: Market badge
const MARKET_BADGE_CONFIG = {
  CN: { label: 'A股', className: 'theme-market-badge--cn' },
  HK: { label: '港股', className: 'theme-market-badge--hk' },
  US: { label: '美股', className: 'theme-market-badge--us' },
  INDEX: { label: '指数', className: 'theme-market-badge--index' },
  ETF: { label: 'ETF', className: 'theme-market-badge--etf' },
  BSE: { label: '北交所', className: 'theme-market-badge--bse' },
} as const;

function MarketBadge({ market }: { market: string }) {
  const config = MARKET_BADGE_CONFIG[market as keyof typeof MARKET_BADGE_CONFIG];

  if (!config) {
    throw new Error(`Unsupported market in stock suggestion: ${market}`);
  }

  return (
    <span className={cn("theme-market-badge", config.className)}>
      {config.label}
    </span>
  );
}

// Helper component: Match type badge
function MatchTypeBadge({ matchType }: { matchType: string }) {
  const configMap = {
    exact: {
      label: '精确',
      className: 'theme-match-badge theme-match-badge--exact',
    },
    prefix: {
      label: '前缀',
      className: 'theme-match-badge theme-match-badge--prefix',
    },
    contains: {
      label: '包含',
      className: 'theme-match-badge theme-match-badge--contains',
    },
    fuzzy: {
      label: '模糊',
      className: 'theme-match-badge',
    },
  };

  const config = configMap[matchType as keyof typeof configMap] || configMap.fuzzy;

  return (
    <span className={cn(config.className)}>
      {config.label}
    </span>
  );
}

export default SuggestionsList;
