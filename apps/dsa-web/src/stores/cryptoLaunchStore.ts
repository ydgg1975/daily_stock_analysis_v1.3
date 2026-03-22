import { create } from "zustand";
import { cryptoApi } from "../api/crypto";
import { cryptoWatchlistApi } from "../api/cryptoWatchlist";
import type {
	CryptoAiSummary,
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
	watchedLaunchIds: Set<number>;
	showWatchedOnly: boolean;

	// Detail
	selectedLaunch: CryptoLaunchDetailResponse | null;
	isLoadingDetail: boolean;
	detailDrawerOpen: boolean;

	// Refresh
	isRefreshing: boolean;
	refreshError: string | null;

	// Status
	scannerStatus: CryptoScannerStatusResponse | null;

	// AI Analysis
	aiSummary: CryptoAiSummary | null;
	isAnalyzing: boolean;
	analyzeError: string | null;

	// Actions
	loadLaunches: (reset?: boolean) => Promise<void>;
	loadMore: () => Promise<void>;
	setSort: (sort: CryptoSortMode) => void;
	setChainFilter: (chains: string[]) => void;
	setMinLiquidity: (value: number) => void;
	setMinVolume: (value: number) => void;
	setMaxAge: (value: number) => void;
	loadWatchedIds: () => Promise<void>;
	toggleWatch: (launchId: number) => Promise<void>;
	setShowWatchedOnly: (value: boolean) => void;
	selectLaunch: (launchId: number) => Promise<void>;
	closeDetail: () => void;
	triggerRefresh: () => Promise<void>;
	loadStatus: () => Promise<void>;
	analyzeToken: (launchId: number) => Promise<void>;
	clearAiSummary: () => void;
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
	watchedLaunchIds: new Set<number>(),
	showWatchedOnly: false,
	selectedLaunch: null as CryptoLaunchDetailResponse | null,
	isLoadingDetail: false,
	detailDrawerOpen: false,
	isRefreshing: false,
	refreshError: null as string | null,
	scannerStatus: null as CryptoScannerStatusResponse | null,
	aiSummary: null as CryptoAiSummary | null,
	isAnalyzing: false,
	analyzeError: null as string | null,
};

// ============ Store ============

export const useCryptoLaunchStore = create<CryptoLaunchState>((set, get) => ({
	...initialState,

	loadLaunches: async (reset = true) => {
		const seq = ++feedRequestSeq;
		const { filters, watchedLaunchIds, showWatchedOnly } = get();

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

			const items = showWatchedOnly
				? response.items.filter((item) => watchedLaunchIds.has(item.id))
				: response.items;

			set({
				launches: items,
				meta: response.meta,
				isLoadingFeed: false,
				feedError: null,
			});

			void get().loadWatchedIds();
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
		const { meta, filters, launches, watchedLaunchIds, showWatchedOnly } =
			get();
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

			const items = showWatchedOnly
				? response.items.filter((item) => watchedLaunchIds.has(item.id))
				: response.items;

			set({
				launches: [...launches, ...items],
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

	loadWatchedIds: async () => {
		try {
			const response = await cryptoWatchlistApi.getWatchedIds();
			set({ watchedLaunchIds: new Set(response.launchIds) });
		} catch {
			// Silent fail for watchlist hydration
		}
	},

	toggleWatch: async (launchId: number) => {
		const { watchedLaunchIds, showWatchedOnly, launches } = get();
		const isWatched = watchedLaunchIds.has(launchId);
		const nextWatchedIds = new Set(watchedLaunchIds);
		let nextLaunches = launches;

		if (isWatched) {
			nextWatchedIds.delete(launchId);
			if (showWatchedOnly) {
				nextLaunches = launches.filter((launch) => launch.id !== launchId);
			}
		} else {
			nextWatchedIds.add(launchId);
		}

		set({ watchedLaunchIds: nextWatchedIds, launches: nextLaunches });

		try {
			if (isWatched) {
				await cryptoWatchlistApi.removeWatch(launchId);
			} else {
				await cryptoWatchlistApi.addWatch(launchId);
			}
		} catch {
			set({ watchedLaunchIds, launches });
		}
	},

	setShowWatchedOnly: (value: boolean) => {
		set({ showWatchedOnly: value });
		if (value) {
			void get()
				.loadWatchedIds()
				.finally(() => get().loadLaunches());
			return;
		}
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

	analyzeToken: async (launchId: number) => {
		set({ isAnalyzing: true, analyzeError: null });

		try {
			const summary = await cryptoApi.analyzeLaunch(launchId);
			set({ aiSummary: summary, isAnalyzing: false });
		} catch (err) {
			set({
				isAnalyzing: false,
				analyzeError: err instanceof Error ? err.message : "AI analysis failed",
			});
		}
	},

	clearAiSummary: () => {
		set({ aiSummary: null, isAnalyzing: false, analyzeError: null });
	},

	resetState: () => {
		feedRequestSeq = 0;
		set(initialState);
	},
}));
