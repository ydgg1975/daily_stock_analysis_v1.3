import type React from 'react';
import { MarketOverviewCard } from './MarketOverviewCard';
import { MarketSentiment } from './MarketSentiment';
import { SectorRankings } from './SectorRankings';
import { MarketSelector } from './MarketSelector';
import { useMarketReview } from '../../hooks/useMarketReview';
import type { MarketType } from '../../types/market';

interface MarketReviewPanelProps {
  className?: string;
}

export const MarketReviewPanel: React.FC<MarketReviewPanelProps> = ({ className = '' }) => {
  const {
    data,
    isLoading,
    error,
    market,
    isAutoRefresh,
    refreshInterval,
    loadMarketReview,
    setMarket,
    toggleAutoRefresh,
    setRefreshInterval,
  } = useMarketReview('cn');

  const handleMarketChange = (newMarket: MarketType) => {
    setMarket(newMarket);
  };

  const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  };

  if (isLoading && !data) {
    return (
      <div className={`flex items-center justify-center min-h-[400px] ${className}`}>
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-muted-text">加载中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`dashboard-card p-6 ${className}`}>
        <div className="text-center">
          <div className="w-12 h-12 rounded-full bg-danger/10 flex items-center justify-center mx-auto mb-3">
            <svg className="w-6 h-6 text-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="text-sm text-danger mb-3">{error.message}</p>
          <button
            type="button"
            onClick={() => void loadMarketReview()}
            className="btn-primary text-sm"
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  if (!data?.overview) {
    return (
      <div className={`dashboard-card p-6 ${className}`}>
        <div className="text-center text-muted-text">
          <p className="text-sm">暂无数据</p>
        </div>
      </div>
    );
  }

  const { overview } = data;

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header with controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-foreground">大盘复盘</h2>
          <p className="text-xs text-muted-text mt-0.5">
            更新时间：{data.updatedAt ? formatTime(data.updatedAt) : '--:--'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <MarketSelector value={market} onChange={handleMarketChange} disabled={isLoading} />
          <button
            type="button"
            onClick={() => void loadMarketReview()}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border/50 bg-muted/30 text-sm font-medium text-foreground hover:bg-hover transition-colors disabled:opacity-50"
            title="刷新"
          >
            <svg className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      {/* Market indices grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {overview.indices.map((index) => (
          <MarketOverviewCard key={index.code} index={index} />
        ))}
      </div>

      {/* Market sentiment */}
      <MarketSentiment sentiment={overview.marketSentiment} />

      {/* Sector rankings */}
      <SectorRankings top={overview.sectorRankings.top} bottom={overview.sectorRankings.bottom} />

      {/* Auto refresh controls */}
      <div className="flex items-center justify-between pt-2 border-t border-border/30">
        <button
          type="button"
          onClick={toggleAutoRefresh}
          className={`inline-flex items-center gap-2 text-xs font-medium transition-colors ${
            isAutoRefresh ? 'text-primary' : 'text-muted-text'
          }`}
        >
          <span className={`w-2 h-2 rounded-full ${isAutoRefresh ? 'bg-primary animate-pulse' : 'bg-muted-text'}`} />
          自动刷新 {isAutoRefresh ? `(每${refreshInterval / 1000}秒)` : ''}
        </button>
        {isAutoRefresh && (
          <select
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            className="text-xs border border-border/50 rounded px-2 py-1 bg-card text-foreground"
          >
            <option value={30000}>30 秒</option>
            <option value={60000}>1 分钟</option>
            <option value={300000}>5 分钟</option>
          </select>
        )}
      </div>
    </div>
  );
};