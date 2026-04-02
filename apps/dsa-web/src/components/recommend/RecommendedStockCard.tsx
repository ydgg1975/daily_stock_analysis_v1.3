import React from 'react';
import { Card, Badge } from '../common';
import type { RecommendedStock } from '../../types/recommendation';
import { TrendingUp, TrendingDown, AlertTriangle, Target, ShieldAlert } from 'lucide-react';

interface RecommendedStockCardProps {
  stock: RecommendedStock;
  rank: number;
}

function scoreBadge(score?: number | null) {
  if (score == null) return null;
  if (score >= 80) return <Badge variant="success" glow>{score}</Badge>;
  if (score >= 60) return <Badge variant="info">{score}</Badge>;
  if (score >= 40) return <Badge variant="warning">{score}</Badge>;
  return <Badge variant="danger">{score}</Badge>;
}

function marketLabel(market: string) {
  const map: Record<string, string> = {
    a_share: 'A 股',
    hk: '港股',
    us: '美股',
  };
  return map[market] || market;
}

export const RecommendedStockCard: React.FC<RecommendedStockCardProps> = ({ stock, rank }) => {
  const changeColor =
    (stock.changePct ?? 0) > 0
      ? 'text-danger'
      : (stock.changePct ?? 0) < 0
        ? 'text-success'
        : 'text-secondary-text';

  const ChangeIcon = (stock.changePct ?? 0) >= 0 ? TrendingUp : TrendingDown;

  return (
    <Card variant="bordered" padding="md" className="space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-cyan/10 text-sm font-bold text-cyan">
            {rank}
          </span>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-foreground">{stock.name}</span>
              <span className="text-xs text-secondary-text">{stock.code}</span>
              <Badge variant="default" size="sm">{marketLabel(stock.market)}</Badge>
            </div>
            {stock.price != null && (
              <div className="mt-0.5 flex items-center gap-2 text-sm">
                <span className="font-medium text-foreground">{stock.price.toFixed(2)}</span>
                {stock.changePct != null && (
                  <span className={`flex items-center gap-0.5 ${changeColor}`}>
                    <ChangeIcon className="h-3 w-3" />
                    {stock.changePct > 0 ? '+' : ''}
                    {stock.changePct.toFixed(2)}%
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
        {scoreBadge(stock.score)}
      </div>

      {/* Reason */}
      {stock.reason && (
        <div className="text-sm text-secondary-text leading-relaxed">{stock.reason}</div>
      )}

      {/* Bottom info */}
      <div className="flex flex-wrap gap-4 text-xs text-secondary-text">
        {stock.targetPrice && (
          <span className="flex items-center gap-1">
            <Target className="h-3 w-3 text-cyan" />
            目标: {stock.targetPrice}
          </span>
        )}
        {stock.stopLoss && (
          <span className="flex items-center gap-1">
            <ShieldAlert className="h-3 w-3 text-warning" />
            止损: {stock.stopLoss}
          </span>
        )}
        {stock.risk && (
          <span className="flex items-center gap-1">
            <AlertTriangle className="h-3 w-3 text-danger" />
            {stock.risk}
          </span>
        )}
      </div>
    </Card>
  );
};
