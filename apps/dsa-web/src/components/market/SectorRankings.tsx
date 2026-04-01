import type React from 'react';
import type { SectorPerformance } from '../../types/market';

interface SectorRankingsProps {
  top: SectorPerformance[];
  bottom: SectorPerformance[];
  className?: string;
}

export const SectorRankings: React.FC<SectorRankingsProps> = ({ top, bottom, className = '' }) => {
  const formatPercent = (num: number) => {
    const prefix = num >= 0 ? '+' : '';
    return `${prefix}${num.toFixed(2)}%`;
  };

  const getChangeColor = (num: number) => {
    if (num > 0) return 'text-success';
    if (num < 0) return 'text-danger';
    return 'text-muted-text';
  };

  const getChangeBg = (num: number) => {
    if (num > 0) return 'bg-success/10';
    if (num < 0) return 'bg-danger/10';
    return 'bg-muted/30';
  };

  const SectorRow: React.FC<{ sector: SectorPerformance; rank: number }> = ({ sector, rank }) => (
    <div className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-hover transition-colors">
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <span className="flex-shrink-0 w-5 text-xs font-medium text-muted-text text-center">{rank}</span>
        <span className="text-sm text-foreground truncate">{sector.name}</span>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {sector.leadingStocks && sector.leadingStocks.length > 0 && (
          <span className="text-xs text-muted-text hidden lg:inline" title={sector.leadingStocks.join(', ')}>
            {sector.leadingStocks[0]}
          </span>
        )}
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getChangeBg(sector.changePercent)} ${getChangeColor(sector.changePercent)}`}>
          {formatPercent(sector.changePercent)}
        </span>
      </div>
    </div>
  );

  return (
    <div className={`dashboard-card p-5 ${className}`}>
      <h3 className="text-sm font-medium text-foreground mb-4">板块涨跌榜</h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Top sectors */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-medium text-success">领涨</span>
            <div className="flex-1 h-px bg-success/20" />
          </div>
          <div className="space-y-1">
            {top.map((sector, index) => (
              <SectorRow key={sector.name} sector={sector} rank={index + 1} />
            ))}
          </div>
        </div>

        {/* Bottom sectors */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-medium text-danger">领跌</span>
            <div className="flex-1 h-px bg-danger/20" />
          </div>
          <div className="space-y-1">
            {bottom.map((sector, index) => (
              <SectorRow key={sector.name} sector={sector} rank={index + 1} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};