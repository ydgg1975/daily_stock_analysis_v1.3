// Market Review Types

export type MarketType = 'cn' | 'us' | 'both';

export interface MarketIndex {
  name: string;
  code: string;
  price: number;
  change: number;
  changePercent: number;
  status: 'up' | 'down' | 'flat';
}

export interface MarketOverview {
  market: MarketType;
  timestamp: string;
  indices: MarketIndex[];
  marketSentiment: {
    advancing: number;
    declining: number;
    unchanged: number;
    limitUp: number;
    limitDown: number;
  };
  sectorRankings: {
    top: SectorPerformance[];
    bottom: SectorPerformance[];
  };
}

export interface SectorPerformance {
  name: string;
  changePercent: number;
  leadingStocks?: string[];
}

export interface MarketReviewResponse {
  overview: MarketOverview;
  updatedAt: string;
  dataSource: string;
}

export interface MarketReviewConfig {
  market: MarketType;
  autoRefresh: boolean;
  refreshInterval: number;
}