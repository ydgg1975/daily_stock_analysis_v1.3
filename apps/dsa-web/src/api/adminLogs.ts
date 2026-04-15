import apiClient from './index';
import { toCamelCase } from './utils';

export interface ExecutionLogEvent {
  id: number;
  eventAt?: string | null;
  phase: string;
  category?: string | null;
  step?: string | null;
  action?: string | null;
  outcome?: string | null;
  reason?: string | null;
  target?: string | null;
  status: string;
  truthLevel: string;
  message?: string | null;
  errorCode?: string | null;
  detail?: Record<string, unknown>;
}

export interface ExecutionLogSessionSummary {
  sessionId: string;
  taskId?: string | null;
  queryId?: string | null;
  analysisHistoryId?: number | null;
  code?: string | null;
  name?: string | null;
  overallStatus: string;
  truthLevel: string;
  startedAt?: string | null;
  endedAt?: string | null;
  summary?: Record<string, unknown>;
  readableSummary?: {
    actorUserId?: string | null;
    actorUsername?: string | null;
    actorDisplay?: string | null;
    actorRole?: string | null;
    sessionKind?: string | null;
    subsystem?: string | null;
    actionName?: string | null;
    destructive?: boolean;
    finalAiModel?: string | null;
    aiAttemptsCount?: number;
    aiFallbackUsed?: boolean;
    finalMarketSource?: string | null;
    finalFundamentalSource?: string | null;
    finalNewsSource?: string | null;
    finalSentimentSource?: string | null;
    dataFallbackUsed?: boolean;
    notificationClassification?: string | null;
    topFailureReason?: string | null;
    scannerRunId?: number | null;
    scannerMarket?: string | null;
    scannerProfile?: string | null;
    scannerProfileLabel?: string | null;
    scannerShortlistCount?: number | null;
    scannerFallbackCount?: number | null;
    scannerProviderFailureCount?: number | null;
    scannerProvidersUsed?: string[];
    scannerCoverageSummary?: string | null;
    summaryParagraph?: string | null;
    status?: string;
  };
}

export interface ExecutionLogSessionDetail extends ExecutionLogSessionSummary {
  events: ExecutionLogEvent[];
}

export interface ExecutionLogSessionListResponse {
  total: number;
  items: ExecutionLogSessionSummary[];
}

export const adminLogsApi = {
  listSessions: async (
    params: {
      stock?: string;
      status?: string;
      category?: string;
      provider?: string;
      model?: string;
      channel?: string;
      limit?: number;
      offset?: number;
    },
  ): Promise<ExecutionLogSessionListResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/admin/logs/sessions',
      {
        params,
      },
    );
    return toCamelCase<ExecutionLogSessionListResponse>(response.data);
  },

  getSessionDetail: async (sessionId: string): Promise<ExecutionLogSessionDetail> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/admin/logs/sessions/${encodeURIComponent(sessionId)}`,
    );
    return toCamelCase<ExecutionLogSessionDetail>(response.data);
  },
};
