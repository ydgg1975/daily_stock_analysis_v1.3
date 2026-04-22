import type React from 'react';
import { useCallback, useRef, useState } from 'react';
import type { EnrichedWatchlistItem } from '../../api/watchlist';
import { cn } from '../../utils/cn';
import { Sparkline } from './Sparkline';
import { HistoryTimeline } from './HistoryTimeline';

interface WatchlistCardProps {
  item: EnrichedWatchlistItem;
  onAnalyze: (stockCode: string) => void;
  onReanalyze: (stockCode: string) => void;
  onRemove: (stockCode: string) => void;
  onMoveGroup: (stockCode: string, groupId: string) => void;
  onMoveItem: (stockCode: string, direction: 'up' | 'down') => void;
  groups: { groupId: string; groupName: string }[];
}

const MARKET_LABELS: Record<string, string> = {
  cn: 'A\u80A1',
  hk: '\u6E2F\u80A1',
  us: '\u7F8E\u80A1',
};

function formatPrice(value: number, market: string): string {
  const currency = market === 'us' ? '$' : market === 'hk' ? 'HK$' : '\u00A5';
  return `${currency}${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPct(value: number): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function sentimentEmoji(score: number): string {
  if (score >= 60) return '\u{1F60A}';
  if (score >= 40) return '\u{1F610}';
  return '\u{1F61F}';
}

function sentimentColorClass(score: number): string {
  if (score >= 60) return 'text-cyan';
  if (score >= 40) return 'text-purple';
  return 'text-danger';
}

function pctColorClass(value: number): string {
  if (value > 0) return 'text-danger';
  if (value < 0) return 'text-success';
  return 'text-muted-text';
}

/**
 * Card component for a single enriched watchlist item.
 */
export const WatchlistCard: React.FC<WatchlistCardProps> = ({
  item,
  onAnalyze,
  onReanalyze,
  onRemove,
  onMoveGroup,
  onMoveItem,
  groups,
}) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const handleMenuToggle = useCallback(() => {
    setMenuOpen((prev) => !prev);
  }, []);

  const closeMenu = useCallback(() => {
    setMenuOpen(false);
  }, []);

  // Close menu when clicking outside
  const handleBlur = useCallback(() => {
    setTimeout(() => {
      if (menuRef.current && !menuRef.current.contains(document.activeElement)) {
        setMenuOpen(false);
      }
    }, 150);
  }, []);

  const otherGroups = groups.filter((g) => g.groupId !== item.groupId);

  return (
    <div className="home-panel-card relative flex flex-col gap-2 px-4 py-4 transition-all hover:shadow-soft-card-strong">
      {/* Header row: name + menu */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-foreground truncate">
            {item.stockName || item.stockCode}
          </p>
          <p className="text-xs text-muted-text font-mono mt-0.5">
            {item.stockCode} &middot; {MARKET_LABELS[item.market] || item.market}
          </p>
        </div>

        {/* Reorder arrows */}
        <div className="flex items-center gap-0.5 shrink-0">
          <button
            type="button"
            onClick={() => onMoveItem(item.stockCode, 'up')}
            className="rounded p-1 text-muted-text transition-colors hover:text-foreground hover:bg-hover"
            aria-label="Move up"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
            </svg>
          </button>
          <button
            type="button"
            onClick={() => onMoveItem(item.stockCode, 'down')}
            className="rounded p-1 text-muted-text transition-colors hover:text-foreground hover:bg-hover"
            aria-label="Move down"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>

        {/* Three-dot menu */}
        <div ref={menuRef} className="relative shrink-0" onBlur={handleBlur}>
          <button
            type="button"
            onClick={handleMenuToggle}
            className="rounded-lg p-1.5 text-muted-text transition-colors hover:text-foreground hover:bg-hover"
            aria-label="More actions"
          >
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
              <circle cx="12" cy="5" r="1.5" />
              <circle cx="12" cy="12" r="1.5" />
              <circle cx="12" cy="19" r="1.5" />
            </svg>
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-full z-20 mt-1 min-w-[160px] rounded-xl border border-border/70 bg-elevated shadow-2xl">
              {otherGroups.length > 0 && (
                <div className="border-b border-border/40 px-3 py-2">
                  <p className="text-xs text-muted-text mb-1">{'\u79FB\u52A8\u5230...'}</p>
                  {otherGroups.map((g) => (
                    <button
                      key={g.groupId}
                      type="button"
                      onClick={() => {
                        onMoveGroup(item.stockCode, g.groupId);
                        closeMenu();
                      }}
                      className="block w-full rounded-lg px-2 py-1.5 text-left text-xs text-secondary-text transition-colors hover:bg-hover hover:text-foreground"
                    >
                      {g.groupName}
                    </button>
                  ))}
                </div>
              )}
              <button
                type="button"
                onClick={() => {
                  onRemove(item.stockCode);
                  closeMenu();
                }}
                className="block w-full rounded-b-xl px-3 py-2 text-left text-xs text-danger transition-colors hover:bg-danger/5"
              >
                {'\u79FB\u9664'}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Price row */}
      {item.price && (
        <div className="flex items-center gap-3">
          <span className="text-lg font-semibold text-foreground">
            {formatPrice(item.price.close, item.market)}
          </span>
          <span className={cn('text-sm font-medium', pctColorClass(item.price.pctChg))}>
            {formatPct(item.price.pctChg)}
          </span>
        </div>
      )}

      {/* Sparkline */}
      {item.sparkline.length > 1 && (
        <Sparkline data={item.sparkline} width={160} height={36} className="w-full" />
      )}

      {/* Sentiment + advice */}
      {item.analysis && (
        <div className="flex items-center gap-2">
          <span className={cn('text-sm font-medium', sentimentColorClass(item.analysis.sentimentScore))}>
            {sentimentEmoji(item.analysis.sentimentScore)} {item.analysis.sentimentScore}
          </span>
          <span className="text-xs text-secondary-text">
            {item.analysis.operationAdvice}
          </span>
        </div>
      )}

      {/* Position */}
      {item.position && (
        <p className="text-xs text-secondary-text">
          {'\u6301\u4ED3'} {item.position.quantity}{'\u80A1'}{' '}
          <span className={cn('font-medium', pctColorClass(item.position.pnlPct))}>
            {formatPct(item.position.pnlPct)}
          </span>
        </p>
      )}

      {/* Expandable analysis history */}
      {item.historyTimeline.length > 0 && (
        <div className="mt-1">
          <button
            type="button"
            onClick={() => setHistoryOpen((prev) => !prev)}
            className="flex items-center gap-1 text-xs text-muted-text transition-colors hover:text-secondary-text"
          >
            <svg
              className={cn('h-3 w-3 transition-transform duration-200', historyOpen && 'rotate-90')}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            {'\u5206\u6790\u5386\u53F2'}
          </button>
          {historyOpen && (
            <div className="mt-2">
              <HistoryTimeline entries={item.historyTimeline} />
            </div>
          )}
        </div>
      )}

      {/* Analyze actions: split into history + reanalyze */}
      <div className="mt-1 flex gap-2">
        <button
          type="button"
          onClick={() => onAnalyze(item.stockCode)}
          className="flex-1 rounded-lg border border-subtle bg-surface/60 px-3 py-1.5 text-xs text-secondary-text transition-colors hover:border-subtle-hover hover:text-foreground"
          title="\u67e5\u770b\u8be5\u80a1\u7968\u7684\u5386\u53f2\u5206\u6790\u62a5\u544a"
        >
          {'\u5206\u6790\u5386\u53f2'}
        </button>
        <button
          type="button"
          onClick={() => onReanalyze(item.stockCode)}
          className="flex-1 rounded-lg border border-cyan/40 bg-cyan/10 px-3 py-1.5 text-xs text-cyan transition-colors hover:border-cyan hover:bg-cyan/20"
          title="\u53d1\u8d77\u4e00\u6b21\u5168\u65b0\u7684 LLM \u5206\u6790"
        >
          {'\u91cd\u65b0\u5206\u6790'}
        </button>
      </div>
    </div>
  );
};
