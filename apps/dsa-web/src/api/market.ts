import apiClient from './index';
import { toCamelCase } from './utils';
import type { MarketReviewResponse, MarketType } from '../types/market';

export interface MarketReviewParams {
  market?: MarketType;
}

export const marketApi = {
  async getMarketOverview(params?: MarketReviewParams): Promise<MarketReviewResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/market/overview', {
      params: {
        market: params?.market || 'cn',
      },
    });
    return toCamelCase<MarketReviewResponse>(response.data);
  },

  async triggerMarketReview(params?: MarketReviewParams): Promise<{ taskId: string }> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/market/review', {
      market: params?.market || 'cn',
    });
    return toCamelCase<{ taskId: string }>(response.data);
  },
};