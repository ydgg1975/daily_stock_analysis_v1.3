import apiClient from './index';
import { toCamelCase } from './utils';
import type { PublicAnalysisPreviewResponse } from '../types/publicAnalysis';

export const publicAnalysisApi = {
  async preview(params: {
    stockCode: string;
    stockName?: string;
    reportType?: 'simple' | 'detailed' | 'full' | 'brief';
    forceRefresh?: boolean;
  }): Promise<PublicAnalysisPreviewResponse> {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/analysis/preview',
      {
        stock_code: params.stockCode,
        stock_name: params.stockName,
        report_type: params.reportType || 'brief',
        force_refresh: Boolean(params.forceRefresh),
      },
      { timeout: 120000 },
    );
    return toCamelCase<PublicAnalysisPreviewResponse>(response.data);
  },
};
