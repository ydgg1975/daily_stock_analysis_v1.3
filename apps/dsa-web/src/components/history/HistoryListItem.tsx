/**
 * SpaceX live refactor: keeps history selection/open behavior untouched while
 * converting each archive row into a quieter spectral list item with uppercase
 * micro-labels, compact metadata, and restrained active/highlight states.
 */
import type React from 'react';
import { useI18n } from '../../contexts/UiLanguageContext';
import type { HistoryItem } from '../../types/analysis';
import { getSentimentColor, getSentimentColorAlpha } from '../../types/analysis';
import { formatDateTime } from '../../utils/format';

interface HistoryListItemProps {
  item: HistoryItem;
  embedded?: boolean;
  manageMode?: boolean;
  isViewing: boolean;
  isHighlighted?: boolean;
  isChecked: boolean;
  isDeleting: boolean;
  onToggleChecked: (recordId: number) => void;
  onClick: (recordId: number) => void;
}

const getOperationBadgeLabel = (advice: string | undefined, fallbackSentiment: string, fallbackAdvice: string) => {
  const normalized = advice?.trim();
  if (!normalized) {
    return fallbackSentiment;
  }
  if (normalized.includes('减仓') || /\b(trim|reduce)\b/i.test(normalized)) {
    return fallbackAdvice;
  }
  if (normalized.includes('卖') || /\b(sell|exit)\b/i.test(normalized)) {
    return fallbackAdvice;
  }
  if (normalized.includes('观望') || normalized.includes('等待') || /\b(wait|watch|hold)\b/i.test(normalized)) {
    return fallbackAdvice;
  }
  if (normalized.includes('买') || normalized.includes('布局') || /\b(buy|build|accumulate)\b/i.test(normalized)) {
    return fallbackAdvice;
  }
  return normalized.split(/[，。；、\s]/)[0] || fallbackAdvice;
};

export const HistoryListItem: React.FC<HistoryListItemProps> = ({
  item,
  embedded = false,
  manageMode = false,
  isViewing,
  isHighlighted = false,
  isChecked,
  isDeleting,
  onToggleChecked,
  onClick,
}) => {
  const { t } = useI18n();
  const score = item.sentimentScore;
  const statusLabel = embedded ? null : t('tasks.completed');
  const displayName = item.stockName || item.stockCode;
  const timestamp = formatDateTime(item.createdAt);

  return (
    <div className="history-archive-item-shell group" data-embedded={embedded ? 'true' : 'false'}>
      {manageMode ? (
        <div className="history-archive-item-shell__check">
          <input
            type="checkbox"
            checked={isChecked}
            onChange={() => onToggleChecked(item.id)}
            disabled={isDeleting}
            className="theme-checkbox"
          />
        </div>
      ) : null}

      <button
        type="button"
        onClick={() => onClick(item.id)}
        data-history-item-id={item.id}
        data-active={isViewing}
        data-highlighted={isHighlighted}
        className="history-archive-item group/item min-w-0 flex-1 text-left transition-all duration-200 ease-out"
      >
        <div className="history-archive-item__content">
          <div className="history-archive-item__header">
            <div className="history-archive-item__identity">
              <div className="history-archive-item__meta">
                <span>{item.stockCode}</span>
                <span className="history-archive-item__divider" aria-hidden="true" />
                <span>{timestamp}</span>
              </div>

              <span className="history-archive-item__title">
                {displayName}
              </span>
            </div>

            <div className="history-archive-item__signals">
              {statusLabel ? (
                <span className="history-archive-item__status">
                  {statusLabel}
                </span>
              ) : null}
              {score !== undefined ? (
                <span
                  className="history-archive-item__badge"
                  style={{
                    color: getSentimentColor(score),
                    borderColor: getSentimentColorAlpha(score, 0.24),
                    backgroundColor: getSentimentColorAlpha(score, 0.1),
                  }}
                >
                  {getOperationBadgeLabel(item.operationAdvice, t('history.sentiment'), t('history.advice'))} {score}
                </span>
              ) : null}
            </div>
          </div>

          {item.operationAdvice ? (
            <p className="history-archive-item__summary">
              {item.operationAdvice}
            </p>
          ) : null}
        </div>
      </button>
    </div>
  );
};
