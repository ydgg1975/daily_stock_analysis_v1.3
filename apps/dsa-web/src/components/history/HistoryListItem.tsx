import type React from 'react';
import { useI18n } from '../../contexts/UiLanguageContext';
import type { HistoryItem } from '../../types/analysis';
import { getSentimentColor, getSentimentColorAlpha } from '../../types/analysis';
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

const getOperationBadgeLabel = (advice: string | undefined, fallbackSentiment: string, fallbackAdvice: string) => {
  const normalized = advice?.trim();
  if (!normalized) {
    return fallbackSentiment;
  }
  if (normalized.includes('减仓')) {
    return fallbackAdvice;
  }
  if (normalized.includes('卖')) {
    return fallbackAdvice;
  }
  if (normalized.includes('观望') || normalized.includes('等待')) {
    return fallbackAdvice;
  }
  if (normalized.includes('买') || normalized.includes('布局')) {
    return fallbackAdvice;
  }
  return normalized.split(/[，。；、\s]/)[0] || fallbackAdvice;
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
  const { t } = useI18n();
  return (
    <div className="group flex items-start gap-2">
      <div className="pt-4">
        <input
          type="checkbox"
          checked={isChecked}
          onChange={() => onToggleChecked(item.id)}
          disabled={isDeleting}
          className="theme-checkbox"
        />
      </div>
      <button
        type="button"
        onClick={() => onClick(item.id)}
        data-history-item-id={item.id}
        data-active={isViewing}
        data-highlighted={isHighlighted}
        className="theme-history-item group/item flex-1 rounded-[0.95rem] border px-3 py-2.5 text-left transition-all duration-200 ease-out"
      >
        <div className="relative z-10 flex items-center gap-2.5">
          {item.sentimentScore !== undefined && (
            <div
              className="w-1 h-8 rounded-full flex-shrink-0"
              style={{
                backgroundColor: getSentimentColor(item.sentimentScore),
                boxShadow: `0 0 10px ${getSentimentColorAlpha(item.sentimentScore, 0.4)}`,
              }}
            />
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <span className="truncate text-[13px] font-semibold tracking-tight text-foreground">
                  {item.stockName || item.stockCode}
                </span>
              </div>
              {item.sentimentScore !== undefined && (
                <span
                  className="shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-semibold leading-none"
                  style={{
                    color: getSentimentColor(item.sentimentScore),
                    borderColor: getSentimentColorAlpha(item.sentimentScore, 0.3),
                    backgroundColor: getSentimentColorAlpha(item.sentimentScore, 0.12),
                  }}
                >
                  {getOperationBadgeLabel(item.operationAdvice, t('history.sentiment'), t('history.advice'))} {item.sentimentScore}
                </span>
              )}
            </div>
            <div className="mt-1 flex items-center gap-2">
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
