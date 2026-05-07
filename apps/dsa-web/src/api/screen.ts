import apiClient from './index';
import { toCamelCase } from './utils';

// ============ Types ============

/** A single stock row returned by the AI screen endpoint. */
export type ScreenResultRow = Record<string, string>;

export interface ScreenResponse {
  success: boolean;
  query: string;
  resultsCount: number;
  returnedCount: number;
  dataSource?: string;
  results: ScreenResultRow[];
  message?: string;
  error?: string;
}

// ============ API ============

export const screenApi = {
  /**
   * Trigger an AI-powered stock screen using natural language conditions.
   * @param query Natural language screening query (e.g. "今天涨幅超过5%的A股")
   */
  query: async (query: string): Promise<ScreenResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/screen/query',
      { query },
    );
    return toCamelCase<ScreenResponse>(response.data);
  },
};

export default screenApi;
