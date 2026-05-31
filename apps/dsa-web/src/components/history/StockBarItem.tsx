import type React from 'react';
import { Badge } from '../common';
import type { StockBarItem as StockBarItemType } from '../../types/analysis';
import { getSentimentColor } from '../../types/analysis';
import { formatDateTime } from '../../utils/format';
import { truncateStockName, isStockNameTruncated } from '../../utils/stockName';

interface StockBarItemProps {
  item: StockBarItemType;
  isViewing: boolean;
  onClick: (recordId: number) => void;
  isMarketReview?: boolean;
}

const getOperationBadgeLabel = (advice?: string) => {
  const normalized = advice?.trim();
  if (!normalized) return null;
  if (normalized.includes('减仓')) return '减仓';
  if (normalized.includes('卖')) return '卖出';
  if (normalized.includes('观望') || normalized.includes('等待')) return '观望';
  if (normalized.includes('买') || normalized.includes('布局')) return '买入';
  return normalized.split(/[，。；、\s]/)[0] || '建议';
};

export const StockBarItemComponent: React.FC<StockBarItemProps> = ({
  item,
  isViewing,
  onClick,
  isMarketReview = false,
}) => {
  const sentimentColor = item.sentimentScore !== undefined ? getSentimentColor(item.sentimentScore) : null;
  const stockName = item.stockName || item.stockCode;
  const isTruncated = isStockNameTruncated(stockName);
  const operationLabel = getOperationBadgeLabel(item.operationAdvice);

  return (
    <button
      type="button"
      onClick={() => onClick(item.id)}
      className={`home-history-item w-full text-left p-2.5 group/item ${
        isViewing ? 'home-history-item-selected' : ''
      }`}
    >
      <div className={`flex items-center gap-2.5 relative z-10${isTruncated ? ' group-hover/item:z-20' : ''}`}>
        {isMarketReview ? (
          <div className="w-1 h-8 rounded-full flex-shrink-0 bg-amber-400" style={{ boxShadow: '0 0 10px rgba(251,191,36,0.4)' }} />
        ) : sentimentColor ? (
          <div
            className="w-1 h-8 rounded-full flex-shrink-0"
            style={{
              backgroundColor: sentimentColor,
              boxShadow: `0 0 10px ${sentimentColor}40`,
            }}
          />
        ) : (
          <div className="w-1 h-8 rounded-full flex-shrink-0 bg-subtle" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <span className="truncate text-sm font-semibold text-foreground tracking-tight">
                <span className="group-hover/item:hidden">
                  {truncateStockName(stockName)}
                </span>
                <span className="hidden group-hover/item:inline">
                  {stockName}
                </span>
              </span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              {isMarketReview ? (
                <Badge
                  variant="default"
                  size="sm"
                  className="shrink-0 shadow-none text-[10px] font-semibold leading-none"
                  style={{
                    color: '#f59e0b',
                    borderColor: 'rgba(245,158,11,0.3)',
                    backgroundColor: 'rgba(245,158,11,0.1)',
                  }}
                >
                  大盘
                </Badge>
              ) : operationLabel && sentimentColor ? (
                <Badge
                  variant="default"
                  size="sm"
                  className="home-history-sentiment-badge shrink-0 shadow-none text-[11px] font-semibold leading-none transition-opacity duration-200"
                  style={{
                    color: sentimentColor,
                    borderColor: `${sentimentColor}30`,
                    backgroundColor: `${sentimentColor}10`,
                  }}
                >
                  {operationLabel} {item.sentimentScore}
                </Badge>
              ) : null}
            </div>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-[11px] text-secondary-text font-mono">
              {item.stockCode}
            </span>
            {item.lastAnalysisTime && (
              <>
                <span className="w-1 h-1 rounded-full bg-subtle-hover" />
                <span className="text-[11px] text-muted-text">
                  {formatDateTime(item.lastAnalysisTime)}
                </span>
              </>
            )}
            {item.analysisCount > 1 && !isMarketReview && (
              <>
                <span className="w-1 h-1 rounded-full bg-subtle-hover" />
                <span className="text-[10px] text-muted-text">
                  {item.analysisCount}次
                </span>
              </>
            )}
          </div>
        </div>
      </div>
    </button>
  );
};
