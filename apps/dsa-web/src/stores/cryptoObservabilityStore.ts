import { create } from "zustand";
import { cryptoApi } from "../api/crypto";
import type {
	AiCostResponse,
	PromptComparisonResponse,
	ProviderMetricsResponse,
	ScanSloResponse,
} from "../types/crypto";

// ============ State Interface ============

export interface CryptoObservabilityState {
	// Data
	providerMetrics: ProviderMetricsResponse | null;
	scanSlo: ScanSloResponse | null;
	aiCost: AiCostResponse | null;
	promptComparison: PromptComparisonResponse | null;

	// Loading
	isLoading: boolean;
	error: string | null;

	// Polling
	pollIntervalMs: number;

	// Actions
	loadAll: () => Promise<void>;
	loadProviderMetrics: () => Promise<void>;
	loadScanSlo: (windowHours?: number) => Promise<void>;
	loadAiCost: (windowDays?: number) => Promise<void>;
	loadPromptComparison: (versions?: string[]) => Promise<void>;
	setPollInterval: (ms: number) => void;
	resetState: () => void;
}

// ============ Initial State ============

const initialState = {
	providerMetrics: null as ProviderMetricsResponse | null,
	scanSlo: null as ScanSloResponse | null,
	aiCost: null as AiCostResponse | null,
	promptComparison: null as PromptComparisonResponse | null,
	isLoading: false,
	error: null as string | null,
	pollIntervalMs: 60_000,
};

const getErrorMessage = (error: unknown, fallback: string): string =>
	error instanceof Error ? error.message : fallback;

// ============ Store ============

export const useCryptoObservabilityStore = create<CryptoObservabilityState>(
	(set, get) => ({
		...initialState,

		loadAll: async () => {
			set({ isLoading: true });
			const results = await Promise.allSettled([
				get().loadProviderMetrics(),
				get().loadScanSlo(),
				get().loadAiCost(),
				get().loadPromptComparison(),
			]);

			const rejectedErrors = results
				.filter(
					(result): result is PromiseRejectedResult =>
						result.status === "rejected",
				)
				.map((result) =>
					getErrorMessage(result.reason, "Failed to load observability data"),
				);

			const stateError = get().error;
			const hasFailure = rejectedErrors.length > 0 || Boolean(stateError);

			if (!hasFailure) {
				set({ isLoading: false, error: null });
				return;
			}

			const aggregatedErrors = Array.from(
				new Set([...(stateError ? [stateError] : []), ...rejectedErrors]),
			).join("; ");

			set({
				isLoading: false,
				error: aggregatedErrors || "Failed to load observability data",
			});
		},

		loadProviderMetrics: async () => {
			try {
				const data = await cryptoApi.getProviderMetrics();
				set({ providerMetrics: data });
			} catch (err) {
				set({
					error: getErrorMessage(err, "Failed to load provider metrics"),
				});
			}
		},

		loadScanSlo: async (windowHours = 24) => {
			try {
				const data = await cryptoApi.getScanSlo(windowHours);
				set({ scanSlo: data });
			} catch (err) {
				set({ error: getErrorMessage(err, "Failed to load scan SLO") });
			}
		},

		loadAiCost: async (windowDays = 7) => {
			try {
				const data = await cryptoApi.getAiCost(windowDays);
				set({ aiCost: data });
			} catch (err) {
				set({ error: getErrorMessage(err, "Failed to load AI cost data") });
			}
		},

		loadPromptComparison: async (versions = ["v1"]) => {
			try {
				const data = await cryptoApi.getPromptComparison(versions);
				set({ promptComparison: data });
			} catch (err) {
				set({
					error: getErrorMessage(err, "Failed to load prompt comparison"),
				});
			}
		},

		setPollInterval: (ms: number) => {
			set({ pollIntervalMs: ms });
		},

		resetState: () => {
			set(initialState);
		},
	}),
);
