import type React from 'react';
import type { MarketOverview } from '../../types/market';

interface MarketSentimentProps {
  sentiment: MarketOverview['marketSentiment'];
  className?: string;
}

export const MarketSentiment: React.FC<MarketSentimentProps> = ({ sentiment, className = '' }) => {
  const total = sentiment.advancing + sentiment.declining + sentiment.unchanged;
  const advancingPct = total > 0 ? (sentiment.advancing / total) * 100 : 0;
  const decliningPct = total > 0 ? (sentiment.declining / total) * 100 : 0;
  const unchangedPct = total > 0 ? (sentiment.unchanged / total) * 100 : 0;

  return (
    <div className={`dashboard-card p-5 ${className}`}>
      <h3 className="text-sm font-medium text-foreground mb-4">市场情绪</h3>
      
      {/* Progress bar */}
      <div className="h-3 w-full rounded-full bg-muted overflow-hidden flex">
        <div 
          className="bg-success transition-all duration-300"
          style={{ width: `${advancingPct}%` }}
          title={`上涨：${sentiment.advancing} (${advancingPct.toFixed(1)}%)`}
        />
        <div 
          className="bg-danger transition-all duration-300"
          style={{ width: `${decliningPct}%` }}
          title={`下跌：${sentiment.declining} (${decliningPct.toFixed(1)}%)`}
        />
        <div 
          className="bg-muted-text/30 transition-all duration-300"
          style={{ width: `${unchangedPct}%` }}
          title={`平盘：${sentiment.unchanged} (${unchangedPct.toFixed(1)}%)`}
        />
      </div>

      {/* Stats grid */}
      <div className="mt-4 grid grid-cols-5 gap-3">
        <div className="text-center">
          <p className="text-xs text-muted-text">上涨</p>
          <p className="text-sm font-semibold text-success">{sentiment.advancing}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-muted-text">下跌</p>
          <p className="text-sm font-semibold text-danger">{sentiment.declining}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-muted-text">平盘</p>
          <p className="text-sm font-semibold text-muted-text">{sentiment.unchanged}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-muted-text">涨停</p>
          <p className="text-sm font-semibold text-success">{sentiment.limitUp}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-muted-text">跌停</p>
          <p className="text-sm font-semibold text-danger">{sentiment.limitDown}</p>
        </div>
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center justify-center gap-4 text-xs text-muted-text">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-success" />
          <span>上涨 {advancingPct.toFixed(1)}%</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-danger" />
          <span>下跌 {decliningPct.toFixed(1)}%</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-muted-text/30" />
          <span>平盘 {unchangedPct.toFixed(1)}%</span>
        </div>
      </div>
    </div>
  );
};