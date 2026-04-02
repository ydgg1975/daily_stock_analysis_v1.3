import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  RecommendTaskAccepted,
  RecommendTaskStatus,
  RecommendHistoryResponse,
  RecommendationResult,
} from '../types/recommendation';

export const recommendationApi = {
  /**
   * Submit a recommendation task (multipart/form-data)
   */
  submit: async (formData: FormData): Promise<RecommendTaskAccepted> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/recommendation/recommend',
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      },
    );
    return toCamelCase<RecommendTaskAccepted>(response.data);
  },

  /**
   * Poll task status
   */
  getStatus: async (taskId: string): Promise<RecommendTaskStatus> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/recommendation/status/${taskId}`,
    );
    return toCamelCase<RecommendTaskStatus>(response.data);
  },

  /**
   * Fetch recommendation history (paginated)
   */
  getHistory: async (params: {
    limit?: number;
    offset?: number;
  } = {}): Promise<RecommendHistoryResponse> => {
    const { limit = 20, offset = 0 } = params;
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/recommendation/history',
      { params: { limit, offset } },
    );
    return toCamelCase<RecommendHistoryResponse>(response.data);
  },

  /**
   * Get single recommendation detail by record ID
   */
  getDetail: async (recordId: number): Promise<RecommendationResult> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/recommendation/${recordId}`,
    );
    return toCamelCase<RecommendationResult>(response.data);
  },
};
