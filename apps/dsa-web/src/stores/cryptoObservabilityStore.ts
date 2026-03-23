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
			set({ isLoading: true, error: null });
			try {
				await Promise.all([
					get().loadProviderMetrics(),
					get().loadScanSlo(),
					get().loadAiCost(),
					get().loadPromptComparison(),
				]);
				set({ isLoading: false });
			} catch (err) {
				set({
					isLoading: false,
					error: getErrorMessage(err, "Failed to load observability data"),
				});
			}
		},

		loadProviderMetrics: async () => {
			try {
				const data = await cryptoApi.getProviderMetrics();
				set({ providerMetrics: data, error: null });
			} catch (err) {
				set({
					error: getErrorMessage(err, "Failed to load provider metrics"),
				});
			}
		},

		loadScanSlo: async (windowHours = 24) => {
			try {
				const data = await cryptoApi.getScanSlo(windowHours);
				set({ scanSlo: data, error: null });
			} catch (err) {
				set({ error: getErrorMessage(err, "Failed to load scan SLO") });
			}
		},

		loadAiCost: async (windowDays = 7) => {
			try {
				const data = await cryptoApi.getAiCost(windowDays);
				set({ aiCost: data, error: null });
			} catch (err) {
				set({ error: getErrorMessage(err, "Failed to load AI cost data") });
			}
		},

		loadPromptComparison: async (versions = ["v1"]) => {
			try {
				const data = await cryptoApi.getPromptComparison(versions);
				set({ promptComparison: data, error: null });
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
