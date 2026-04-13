import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  ScannerOperationalStatus,
  ScannerRunDetail,
  ScannerRunHistoryResponse,
  ScannerRunRequest,
} from '../types/scanner';

export const scannerApi = {
  run: async (params: ScannerRunRequest = {}): Promise<ScannerRunDetail> => {
    const requestData: Record<string, unknown> = {
      market: params.market || 'cn',
    };
    if (params.profile) requestData.profile = params.profile;
    if (params.shortlistSize != null) requestData.shortlist_size = params.shortlistSize;
    if (params.universeLimit != null) requestData.universe_limit = params.universeLimit;
    if (params.detailLimit != null) requestData.detail_limit = params.detailLimit;

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/scanner/run',
      requestData,
      { timeout: 120000 },
    );
    return toCamelCase<ScannerRunDetail>(response.data);
  },

  getRuns: async (params: {
    market?: string;
    profile?: string;
    page?: number;
    limit?: number;
  } = {}): Promise<ScannerRunHistoryResponse> => {
    const {
      market = 'cn',
      profile,
      page = 1,
      limit = 10,
    } = params;
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/scanner/runs',
      {
        params: {
          market,
          profile,
          page,
          limit,
        },
      },
    );
    return toCamelCase<ScannerRunHistoryResponse>(response.data);
  },

  getRun: async (runId: number): Promise<ScannerRunDetail> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/scanner/runs/${encodeURIComponent(runId)}`,
    );
    return toCamelCase<ScannerRunDetail>(response.data);
  },

  getTodayWatchlist: async (params: {
    market?: string;
    profile?: string;
  } = {}): Promise<ScannerRunDetail> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/scanner/watchlists/today',
      {
        params: {
          market: params.market || 'cn',
          profile: params.profile,
        },
      },
    );
    return toCamelCase<ScannerRunDetail>(response.data);
  },

  getRecentWatchlists: async (params: {
    market?: string;
    profile?: string;
    limitDays?: number;
  } = {}): Promise<ScannerRunHistoryResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/scanner/watchlists/recent',
      {
        params: {
          market: params.market || 'cn',
          profile: params.profile,
          limit_days: params.limitDays ?? 7,
        },
      },
    );
    return toCamelCase<ScannerRunHistoryResponse>(response.data);
  },

  getStatus: async (params: {
    market?: string;
    profile?: string;
  } = {}): Promise<ScannerOperationalStatus> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/scanner/status',
      {
        params: {
          market: params.market || 'cn',
          profile: params.profile,
        },
      },
    );
    return toCamelCase<ScannerOperationalStatus>(response.data);
  },
};
