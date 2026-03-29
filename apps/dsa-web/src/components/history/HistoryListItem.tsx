import type React from 'react';
import type { HistoryItem } from '../../types/analysis';
import { getSentimentColor } from '../../types/analysis';
import { formatDateTime } from '../../utils/format';

interface HistoryListItemProps {
  item: HistoryItem;
  isViewing: boolean; // Indicates if this report is currently being viewed in the right panel
  isHighlighted?: boolean;
  isChecked: boolean; // Indicates if the checkbox is checked for bulk operations
  isDeleting: boolean;
  onToggleChecked: (recordId: number) => void;
  onClick: (recordId: number) => void;
}

const getOperationBadgeLabel = (advice?: string) => {
  const normalized = advice?.trim();
  if (!normalized) {
    return '情绪';
  }
  if (normalized.includes('减仓')) {
    return '减仓';
  }
  if (normalized.includes('卖')) {
    return '卖出';
  }
  if (normalized.includes('观望') || normalized.includes('等待')) {
    return '观望';
  }
  if (normalized.includes('买') || normalized.includes('布局')) {
    return '买入';
  }
  return normalized.split(/[，。；、\s]/)[0] || '建议';
};

export const HistoryListItem: React.FC<HistoryListItemProps> = ({
  item,
  isViewing,
  isHighlighted = false,
  isChecked,
  isDeleting,
  onToggleChecked,
  onClick,
}) => {
  return (
    <div className="flex items-start gap-2 group">
      <div className="pt-5">
        <input
          type="checkbox"
          checked={isChecked}
          onChange={() => onToggleChecked(item.id)}
          disabled={isDeleting}
          className="h-3.5 w-3.5 cursor-pointer rounded border-white/10 bg-transparent text-cyan focus:ring-cyan/30 disabled:opacity-50"
        />
      </div>
      <button
        type="button"
        onClick={() => onClick(item.id)}
        data-history-item-id={item.id}
        data-active={isViewing}
        data-highlighted={isHighlighted}
        className="theme-history-item group/item flex-1 rounded-[0.95rem] border p-3 text-left transition-all duration-200 ease-out"
      >
        <div className="flex items-center gap-2.5 relative z-10">
          {item.sentimentScore !== undefined && (
            <div
              className="w-1 h-8 rounded-full flex-shrink-0"
              style={{
                backgroundColor: getSentimentColor(item.sentimentScore),
                boxShadow: `0 0 10px ${getSentimentColor(item.sentimentScore)}40`,
              }}
            />
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <span className="truncate text-sm font-semibold text-foreground tracking-tight">
                  {item.stockName || item.stockCode}
                </span>
              </div>
              {item.sentimentScore !== undefined && (
                <span
                  className="shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-semibold leading-none"
                  style={{
                    color: getSentimentColor(item.sentimentScore),
                    borderColor: `${getSentimentColor(item.sentimentScore)}30`,
                    backgroundColor: `${getSentimentColor(item.sentimentScore)}10`,
                  }}
                >
                  {getOperationBadgeLabel(item.operationAdvice)} {item.sentimentScore}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[11px] text-secondary-text font-mono">
                {item.stockCode}
              </span>
              <span className="w-1 h-1 rounded-full bg-subtle-hover" />
              <span className="text-[11px] text-muted-text">
                {formatDateTime(item.createdAt)}
              </span>
            </div>
          </div>
        </div>
      </button>
    </div>
  );
};
