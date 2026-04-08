import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  BacktestRunRequest,
  BacktestRunResponse,
  BacktestRunHistoryResponse,
  BacktestResultsResponse,
  BacktestResultItem,
  PerformanceMetrics,
  PrepareBacktestSamplesRequest,
  PrepareBacktestSamplesResponse,
  BacktestSampleStatusResponse,
  BacktestClearResponse,
  RuleBacktestParseRequest,
  RuleBacktestParseResponse,
  RuleBacktestRunRequest,
  RuleBacktestRunResponse,
  RuleBacktestHistoryResponse,
} from '../types/backtest';

// ============ API ============

export const backtestApi = {
  parseRuleStrategy: async (params: RuleBacktestParseRequest): Promise<RuleBacktestParseResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/backtest/rule/parse',
      { code: params.code, strategy_text: params.strategyText },
    );
    return toCamelCase<RuleBacktestParseResponse>(response.data);
  },

  runRuleBacktest: async (params: RuleBacktestRunRequest): Promise<RuleBacktestRunResponse> => {
    const requestData: Record<string, unknown> = {
      code: params.code,
      strategy_text: params.strategyText,
      confirmed: params.confirmed || false,
    };
    if (params.parsedStrategy) requestData.parsed_strategy = params.parsedStrategy;
    if (params.lookbackBars != null) requestData.lookback_bars = params.lookbackBars;
    if (params.initialCapital != null) requestData.initial_capital = params.initialCapital;
    if (params.feeBps != null) requestData.fee_bps = params.feeBps;
    if (params.slippageBps != null) requestData.slippage_bps = params.slippageBps;
    if (params.waitForCompletion != null) requestData.wait_for_completion = params.waitForCompletion;

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/backtest/rule/run',
      requestData,
    );
    return toCamelCase<RuleBacktestRunResponse>(response.data);
  },

  getRuleBacktestRuns: async (params: { code?: string; page?: number; limit?: number } = {}): Promise<RuleBacktestHistoryResponse> => {
    const { code, page = 1, limit = 20 } = params;
    const queryParams: Record<string, string | number> = { page, limit };
    if (code) queryParams.code = code;
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/backtest/rule/runs',
      { params: queryParams },
    );
    return toCamelCase<RuleBacktestHistoryResponse>(response.data);
  },

  getRuleBacktestRun: async (runId: number): Promise<RuleBacktestRunResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/backtest/rule/runs/${encodeURIComponent(runId)}`,
    );
    return toCamelCase<RuleBacktestRunResponse>(response.data);
  },

  /**
   * Trigger backtest evaluation
   */
  run: async (params: BacktestRunRequest = {}): Promise<BacktestRunResponse> => {
    const requestData: Record<string, unknown> = {};
    if (params.code) requestData.code = params.code;
    if (params.force != null) requestData.force = params.force;
    if (params.evalWindowDays != null) requestData.eval_window_days = params.evalWindowDays;
    if (params.minAgeDays != null) requestData.min_age_days = params.minAgeDays;
    if (params.limit != null) requestData.limit = params.limit;

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/backtest/run',
      requestData,
    );
    return toCamelCase<BacktestRunResponse>(response.data);
  },

  /**
   * Prepare historical analysis samples for backtesting
   */
  prepareSamples: async (params: PrepareBacktestSamplesRequest): Promise<PrepareBacktestSamplesResponse> => {
    const requestData: Record<string, unknown> = { code: params.code };
    if (params.sampleCount != null) requestData.sample_count = params.sampleCount;
    if (params.evalWindowDays != null) requestData.eval_window_days = params.evalWindowDays;
    if (params.minAgeDays != null) requestData.min_age_days = params.minAgeDays;
    if (params.forceRefresh != null) requestData.force_refresh = params.forceRefresh;

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/backtest/prepare-samples',
      requestData,
    );
    return toCamelCase<PrepareBacktestSamplesResponse>(response.data);
  },

  getSampleStatus: async (code: string): Promise<BacktestSampleStatusResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/backtest/sample-status',
      { params: { code } },
    );
    return toCamelCase<BacktestSampleStatusResponse>(response.data);
  },

  getHistory: async (params: { code?: string; page?: number; limit?: number } = {}): Promise<BacktestRunHistoryResponse> => {
    const { code, page = 1, limit = 20 } = params;
    const queryParams: Record<string, string | number> = { page, limit };
    if (code) queryParams.code = code;

    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/backtest/runs',
      { params: queryParams },
    );

    return toCamelCase<BacktestRunHistoryResponse>(response.data);
  },

  clearSamples: async (code: string): Promise<BacktestClearResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/backtest/samples/clear',
      { code },
    );
    return toCamelCase<BacktestClearResponse>(response.data);
  },

  clearResults: async (code: string): Promise<BacktestClearResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/backtest/results/clear',
      { code },
    );
    return toCamelCase<BacktestClearResponse>(response.data);
  },

  /**
   * Get paginated backtest results
   */
  getResults: async (params: {
    code?: string;
    evalWindowDays?: number;
    runId?: number;
    page?: number;
    limit?: number;
  } = {}): Promise<BacktestResultsResponse> => {
    const { code, evalWindowDays, runId, page = 1, limit = 20 } = params;

    const queryParams: Record<string, string | number> = { page, limit };
    if (code) queryParams.code = code;
    if (evalWindowDays) queryParams.eval_window_days = evalWindowDays;
    if (runId) queryParams.run_id = runId;

    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/backtest/results',
      { params: queryParams },
    );

    const data = toCamelCase<BacktestResultsResponse>(response.data);
    return {
      total: data.total,
      page: data.page,
      limit: data.limit,
      items: (data.items || []).map(item => toCamelCase<BacktestResultItem>(item)),
    };
  },

  /**
   * Get overall performance metrics
   */
  getOverallPerformance: async (evalWindowDays?: number): Promise<PerformanceMetrics | null> => {
    try {
      const params: Record<string, number> = {};
      if (evalWindowDays) params.eval_window_days = evalWindowDays;
      const response = await apiClient.get<Record<string, unknown>>(
        '/api/v1/backtest/performance',
        { params },
      );
      return toCamelCase<PerformanceMetrics>(response.data);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number } };
        if (axiosErr.response?.status === 404) return null;
      }
      throw err;
    }
  },

  /**
   * Get per-stock performance metrics
   */
  getStockPerformance: async (code: string, evalWindowDays?: number): Promise<PerformanceMetrics | null> => {
    try {
      const params: Record<string, number> = {};
      if (evalWindowDays) params.eval_window_days = evalWindowDays;
      const response = await apiClient.get<Record<string, unknown>>(
        `/api/v1/backtest/performance/${encodeURIComponent(code)}`,
        { params },
      );
      return toCamelCase<PerformanceMetrics>(response.data);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number } };
        if (axiosErr.response?.status === 404) return null;
      }
      throw err;
    }
  },
};
