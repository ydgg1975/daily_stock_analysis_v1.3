import { create } from "zustand";
import { cryptoApi } from "../api/crypto";
import type {
	CryptoFilters,
	CryptoLaunchDetailResponse,
	CryptoLaunchRow,
	CryptoScannerStatusResponse,
	CryptoSortMode,
	FeedMeta,
} from "../types/crypto";

// ============ State Interface ============

let feedRequestSeq = 0;

export interface CryptoLaunchState {
	// Feed
	launches: CryptoLaunchRow[];
	meta: FeedMeta | null;
	isLoadingFeed: boolean;
	feedError: string | null;

	// Filters
	filters: CryptoFilters;

	// Detail
	selectedLaunch: CryptoLaunchDetailResponse | null;
	isLoadingDetail: boolean;
	detailDrawerOpen: boolean;

	// Refresh
	isRefreshing: boolean;
	refreshError: string | null;

	// Status
	scannerStatus: CryptoScannerStatusResponse | null;

	// Actions
	loadLaunches: (reset?: boolean) => Promise<void>;
	loadMore: () => Promise<void>;
	setSort: (sort: CryptoSortMode) => void;
	setChainFilter: (chains: string[]) => void;
	setMinLiquidity: (value: number) => void;
	setMinVolume: (value: number) => void;
	setMaxAge: (value: number) => void;
	selectLaunch: (launchId: number) => Promise<void>;
	closeDetail: () => void;
	triggerRefresh: () => Promise<void>;
	loadStatus: () => Promise<void>;
	resetState: () => void;
}

// ============ Initial State ============

const defaultFilters: CryptoFilters = {
	chains: [],
	minLiquidityUsd: 0,
	minVolumeUsd: 0,
	maxAgeMinutes: 1440,
	sort: "newest",
};

const initialState = {
	launches: [] as CryptoLaunchRow[],
	meta: null as FeedMeta | null,
	isLoadingFeed: false,
	feedError: null as string | null,
	filters: { ...defaultFilters },
	selectedLaunch: null as CryptoLaunchDetailResponse | null,
	isLoadingDetail: false,
	detailDrawerOpen: false,
	isRefreshing: false,
	refreshError: null as string | null,
	scannerStatus: null as CryptoScannerStatusResponse | null,
};

// ============ Store ============

export const useCryptoLaunchStore = create<CryptoLaunchState>((set, get) => ({
	...initialState,

	loadLaunches: async (reset = true) => {
		const seq = ++feedRequestSeq;
		const { filters } = get();

		if (reset) {
			set({ isLoadingFeed: true, feedError: null });
		}

		try {
			const response = await cryptoApi.getLaunches({
				chains: filters.chains.length ? filters.chains : undefined,
				minLiquidityUsd: filters.minLiquidityUsd || undefined,
				minVolumeUsd: filters.minVolumeUsd || undefined,
				maxAgeMinutes: filters.maxAgeMinutes,
				sort: filters.sort,
				limit: 50,
			});

			if (seq !== feedRequestSeq) return; // Stale request

			set({
				launches: response.items,
				meta: response.meta,
				isLoadingFeed: false,
				feedError: null,
			});
		} catch (err) {
			if (seq !== feedRequestSeq) return;
			set({
				isLoadingFeed: false,
				feedError:
					err instanceof Error ? err.message : "Failed to load launches",
			});
		}
	},

	loadMore: async () => {
		const { meta, filters, launches } = get();
		if (!meta?.nextCursor) return;

		const seq = ++feedRequestSeq;

		try {
			const response = await cryptoApi.getLaunches({
				chains: filters.chains.length ? filters.chains : undefined,
				minLiquidityUsd: filters.minLiquidityUsd || undefined,
				minVolumeUsd: filters.minVolumeUsd || undefined,
				maxAgeMinutes: filters.maxAgeMinutes,
				sort: filters.sort,
				cursor: meta.nextCursor,
				limit: 50,
			});

			if (seq !== feedRequestSeq) return;

			set({
				launches: [...launches, ...response.items],
				meta: response.meta,
			});
		} catch {
			// Silent fail for load-more
		}
	},

	setSort: (sort: CryptoSortMode) => {
		set((state) => ({ filters: { ...state.filters, sort } }));
		void get().loadLaunches();
	},

	setChainFilter: (chains: string[]) => {
		set((state) => ({ filters: { ...state.filters, chains } }));
		void get().loadLaunches();
	},

	setMinLiquidity: (value: number) => {
		set((state) => ({ filters: { ...state.filters, minLiquidityUsd: value } }));
		void get().loadLaunches();
	},

	setMinVolume: (value: number) => {
		set((state) => ({ filters: { ...state.filters, minVolumeUsd: value } }));
		void get().loadLaunches();
	},

	setMaxAge: (value: number) => {
		set((state) => ({ filters: { ...state.filters, maxAgeMinutes: value } }));
		void get().loadLaunches();
	},

	selectLaunch: async (launchId: number) => {
		set({ isLoadingDetail: true, detailDrawerOpen: true });

		try {
			const detail = await cryptoApi.getLaunchDetail(launchId);
			set({ selectedLaunch: detail, isLoadingDetail: false });
		} catch {
			set({ isLoadingDetail: false });
		}
	},

	closeDetail: () => {
		set({ detailDrawerOpen: false, selectedLaunch: null });
	},

	triggerRefresh: async () => {
		set({ isRefreshing: true, refreshError: null });

		try {
			await cryptoApi.triggerRefresh();
			set({ isRefreshing: false });
			// Reload feed after refresh
			void get().loadLaunches();
		} catch (err) {
			set({
				isRefreshing: false,
				refreshError: err instanceof Error ? err.message : "Refresh failed",
			});
		}
	},

	loadStatus: async () => {
		try {
			const status = await cryptoApi.getStatus();
			set({ scannerStatus: status });
		} catch {
			// Silent fail for status
		}
	},

	resetState: () => {
		feedRequestSeq = 0;
		set(initialState);
	},
}));
