import { useCallback, useEffect, useState } from 'react';
import { marketApi } from '../api/market';
import type { MarketReviewResponse, MarketType } from '../types/market';

export interface UseMarketReviewState {
  data: MarketReviewResponse | null;
  isLoading: boolean;
  error: Error | null;
  market: MarketType;
  isAutoRefresh: boolean;
  refreshInterval: number;
}

export interface UseMarketReviewActions {
  loadMarketReview: (market?: MarketType) => Promise<void>;
  setMarket: (market: MarketType) => void;
  toggleAutoRefresh: () => void;
  setRefreshInterval: (interval: number) => void;
  clearError: () => void;
}

export type UseMarketReviewReturn = UseMarketReviewState & UseMarketReviewActions;

export function useMarketReview(initialMarket: MarketType = 'cn'): UseMarketReviewReturn {
  const [data, setData] = useState<MarketReviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [market, setMarket] = useState<MarketType>(initialMarket);
  const [isAutoRefresh, setIsAutoRefresh] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState(60000); // 1 minute default

  const loadMarketReview = useCallback(async (marketParam?: MarketType) => {
    const targetMarket = marketParam ?? market;
    setIsLoading(true);
    setError(null);
    try {
      const result = await marketApi.getMarketOverview({ market: targetMarket });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load market review'));
      setData(null);
    } finally {
      setIsLoading(false);
    }
  }, [market]);

  const toggleAutoRefresh = useCallback(() => {
    setIsAutoRefresh((prev) => !prev);
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Initial load and reload when market changes
  useEffect(() => {
    void loadMarketReview(market);
  }, [market, loadMarketReview]);

  // Auto refresh
  useEffect(() => {
    if (!isAutoRefresh) {
      return;
    }

    const timer = setInterval(() => {
      void loadMarketReview(market);
    }, refreshInterval);

    return () => {
      clearInterval(timer);
    };
  }, [isAutoRefresh, refreshInterval, market, loadMarketReview]);

  return {
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
    clearError,
  };
}