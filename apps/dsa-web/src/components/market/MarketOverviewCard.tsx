import type React from 'react';
import type { MarketIndex } from '../../types/market';

interface MarketOverviewCardProps {
  index: MarketIndex;
  className?: string;
}

export const MarketOverviewCard: React.FC<MarketOverviewCardProps> = ({ index, className = '' }) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'up':
        return 'text-success';
      case 'down':
        return 'text-danger';
      default:
        return 'text-muted-text';
    }
  };

  const getStatusBg = (status: string) => {
    switch (status) {
      case 'up':
        return 'bg-success/10';
      case 'down':
        return 'bg-danger/10';
      default:
        return 'bg-muted/30';
    }
  };

  const formatNumber = (num: number, isPercent = false) => {
    const absNum = Math.abs(num);
    if (absNum >= 10000) {
      return (num / 10000).toFixed(2) + 'k';
    }
    return num.toFixed(2) + (isPercent ? '%' : '');
  };

  const changePrefix = index.change >= 0 ? '+' : '';
  const changePercentPrefix = index.changePercent >= 0 ? '+' : '';

  return (
    <div className={`dashboard-card p-4 ${className}`}>
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-medium text-foreground truncate">{index.name}</h3>
          <p className="text-xs text-muted-text mt-0.5">{index.code}</p>
        </div>
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getStatusBg(index.status)} ${getStatusColor(index.status)}`}>
          {index.status === 'up' ? '↑' : index.status === 'down' ? '↓' : '−'}
        </span>
      </div>
      <div className="mt-3">
        <p className="text-lg font-semibold text-foreground">{formatNumber(index.price)}</p>
        <div className="mt-1 flex items-center gap-2">
          <span className={`text-xs font-medium ${getStatusColor(index.status)}`}>
            {changePrefix}{formatNumber(index.change)}
          </span>
          <span className={`text-xs font-medium ${getStatusColor(index.status)}`}>
            ({changePercentPrefix}{formatNumber(index.changePercent, true)}%)
          </span>
        </div>
      </div>
    </div>
  );
};