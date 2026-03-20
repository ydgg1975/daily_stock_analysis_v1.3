import type {
	CryptoLaunchDetailResponse,
	CryptoLaunchFeedResponse,
	CryptoRefreshResponse,
	CryptoScannerStatusResponse,
	CryptoSortMode,
} from "../types/crypto";
import apiClient from "./index";
import { toCamelCase } from "./utils";

// ============ API Interface ============

export const cryptoApi = {
	/**
	 * Fetch paginated crypto launches with optional filters.
	 */
	getLaunches: async (params?: {
		chains?: string[];
		minLiquidityUsd?: number;
		minVolumeUsd?: number;
		maxAgeMinutes?: number;
		sort?: CryptoSortMode;
		cursor?: number;
		limit?: number;
	}): Promise<CryptoLaunchFeedResponse> => {
		const query: Record<string, string | number> = {};
		if (params?.chains?.length) query.chains = params.chains.join(",");
		if (params?.minLiquidityUsd)
			query.min_liquidity_usd = params.minLiquidityUsd;
		if (params?.minVolumeUsd) query.min_volume_usd = params.minVolumeUsd;
		if (params?.maxAgeMinutes) query.max_age_minutes = params.maxAgeMinutes;
		if (params?.sort) query.sort = params.sort;
		if (params?.cursor) query.cursor = params.cursor;
		if (params?.limit) query.limit = params.limit;

		const response = await apiClient.get<Record<string, unknown>>(
			"/api/v1/crypto/launches",
			{
				params: query,
			},
		);
		return toCamelCase<CryptoLaunchFeedResponse>(response.data);
	},

	/**
	 * Fetch a single launch detail with its recent snapshots.
	 */
	getLaunchDetail: async (
		launchId: number,
	): Promise<CryptoLaunchDetailResponse> => {
		const response = await apiClient.get<Record<string, unknown>>(
			`/api/v1/crypto/launches/${launchId}`,
		);
		return toCamelCase<CryptoLaunchDetailResponse>(response.data);
	},

	/**
	 * Manually trigger a scan cycle.
	 */
	triggerRefresh: async (chains?: string[]): Promise<CryptoRefreshResponse> => {
		const body = chains?.length ? { chains } : {};
		const response = await apiClient.post<Record<string, unknown>>(
			"/api/v1/crypto/refresh",
			body,
		);
		return toCamelCase<CryptoRefreshResponse>(response.data);
	},

	/**
	 * Get current scanner runtime status.
	 */
	getStatus: async (): Promise<CryptoScannerStatusResponse> => {
		const response = await apiClient.get<Record<string, unknown>>(
			"/api/v1/crypto/status",
		);
		return toCamelCase<CryptoScannerStatusResponse>(response.data);
	},
};
