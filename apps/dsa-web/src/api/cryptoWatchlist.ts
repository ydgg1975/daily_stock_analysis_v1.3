import type { WatchedIdsResponse } from "../types/crypto";
import apiClient from "./index";
import { toCamelCase } from "./utils";

export const cryptoWatchlistApi = {
	getWatchedIds: async (): Promise<WatchedIdsResponse> => {
		const response = await apiClient.get<Record<string, unknown>>(
			"/api/v1/crypto/watchlist/ids",
		);
		return toCamelCase<WatchedIdsResponse>(response.data);
	},

	addWatch: async (launchId: number, note?: string) => {
		const body = note ? { note } : {};
		const response = await apiClient.post<Record<string, unknown>>(
			`/api/v1/crypto/watchlist/${launchId}`,
			body,
		);
		return toCamelCase(response.data);
	},

	removeWatch: async (launchId: number) => {
		const response = await apiClient.delete<Record<string, unknown>>(
			`/api/v1/crypto/watchlist/${launchId}`,
		);
		return toCamelCase(response.data);
	},
};
