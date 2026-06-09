import apiClient from './index';
import { toCamelCase } from './utils';

export interface CallTypeBreakdown {
  callType: string;
  calls: number;
  totalTokens: number;
}

export interface ModelBreakdown {
  model: string;
  calls: number;
  totalTokens: number;
}

export interface UsageSummary {
  period: string;
  fromDate: string;
  toDate: string;
  totalCalls: number;
  totalTokens: number;
  byCallType: CallTypeBreakdown[];
  byModel: ModelBreakdown[];
}

export type UsagePeriod = 'today' | 'month' | 'all';

export const usageApi = {
  async getSummary(period: UsagePeriod = 'month'): Promise<UsageSummary> {
    const res = await apiClient.get('/api/v1/usage/summary', { params: { period } });
    return toCamelCase<UsageSummary>(res.data);
  },
};
