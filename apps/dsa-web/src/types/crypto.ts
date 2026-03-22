/**
 * Crypto scanner type definitions
 * Aligned with api/v1/schemas/crypto.py
 */

// ============ Launch Types ============

/** A single crypto launch row in the feed */
export interface CryptoLaunchRow {
	id: number;
	chainId: string;
	dexId?: string | null;
	pairAddress: string;
	pairUrl?: string | null;
	pairCreatedAt?: string | null;

	baseTokenAddress?: string | null;
	baseTokenSymbol?: string | null;
	baseTokenName?: string | null;
	quoteTokenAddress?: string | null;
	quoteTokenSymbol?: string | null;
	quoteTokenName?: string | null;

	liquidityUsd?: number | null;
	volumeUsd24h?: number | null;
	buys24h?: number | null;
	sells24h?: number | null;
	priceUsd?: number | null;
	priceChangePct24h?: number | null;
	fdvUsd?: number | null;
	marketCapUsd?: number | null;

	dexscreenerUrl?: string | null;
	websiteUrl?: string | null;
	socialsJson?: string | null;
	labelsJson?: string | null;
	dataComplete: boolean;

	firstSeenAt?: string | null;
	lastSeenAt?: string | null;
	createdAt?: string | null;
	updatedAt?: string | null;
	riskScore?: number | null;
	riskLevel?: string | null;
}

/** A snapshot entry for the detail view */
export interface CryptoSnapshotRow {
	id: number;
	launchId: number;
	snapshotAt?: string | null;
	liquidityUsd?: number | null;
	volumeUsd24h?: number | null;
	buys24h?: number | null;
	sells24h?: number | null;
	priceUsd?: number | null;
	priceChangePct24h?: number | null;
	fdvUsd?: number | null;
	marketCapUsd?: number | null;
	dataComplete: boolean;
}

// ============ Feed Types ============

/** Feed response metadata */
export interface FeedMeta {
	total: number;
	nextCursor?: number | null;
	chains: string[];
	sort: string;
	dataComplete: boolean;
	symbolsPartial: boolean;
}

/** Response for GET /api/v1/crypto/launches */
export interface CryptoLaunchFeedResponse {
	items: CryptoLaunchRow[];
	meta: FeedMeta;
}

// ============ Detail Types ============

/** Response for GET /api/v1/crypto/launches/{launch_id} */
export interface CryptoLaunchDetailResponse {
	launch: CryptoLaunchRow;
	snapshots: CryptoSnapshotRow[];
}

// ============ Refresh Types ============

/** Request body for POST /api/v1/crypto/refresh */
export interface CryptoRefreshRequest {
	chains?: string[];
}

/** Response for POST /api/v1/crypto/refresh */
export interface CryptoRefreshResponse {
	status: string;
	message: string;
	new: number;
	updated: number;
	failedChains: string[];
}

// ============ Status Types ============

/** Response for GET /api/v1/crypto/status */
export interface CryptoScannerStatusResponse {
	enabled: boolean;
	isScanning: boolean;
	refreshIntervalSec: number;
	enabledChains: string[];
	lastScanAt?: string | null;
	lastScanDurationSec: number;
	lastScanChains: string[];
	lastScanFailedChains: string[];
	lastScanNewLaunches: number;
	lastScanUpdatedLaunches: number;
	totalScans: number;
}

// ============ Filter Types ============

export type CryptoSortMode = "newest" | "liquidity" | "volume" | "activity";

export interface CryptoFilters {
	chains: string[];
	minLiquidityUsd: number;
	minVolumeUsd: number;
	maxAgeMinutes: number;
	sort: CryptoSortMode;
}

// ============ Watchlist Types ============

export interface WatchedIdsResponse {
	launchIds: number[];
}

// ============ AI Summary Types ============

/** Response for POST /api/v1/crypto/launches/{id}/analyze */
export interface CryptoAiSummary {
	launchId: number;
	verdict?: string | null; // BUY, HOLD, AVOID
	confidence?: number | null; // 0.0 - 1.0
	bullCase?: string | null;
	bearCase?: string | null;
	risks?: string[] | null;
	recommendedAction?: string | null;
	modelUsed?: string | null;
	promptVersion: string;
	analyzedAt?: string | null;
	error?: string | null;
	cached: boolean;
}

// ============ Helpers ============

/** Format a chain ID for display (capitalize first letter) */
export const formatChainLabel = (chainId: string): string => {
	return chainId.charAt(0).toUpperCase() + chainId.slice(1);
};

/** Format a USD value for compact display */
export const formatUsd = (value: number | null | undefined): string => {
	if (value == null) return "-";
	if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
	if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
	if (value >= 1) return `$${value.toFixed(2)}`;
	return `$${value.toFixed(6)}`;
};

/** Format a percentage change */
export const formatPctChange = (value: number | null | undefined): string => {
	if (value == null) return "-";
	const sign = value >= 0 ? "+" : "";
	return `${sign}${value.toFixed(2)}%`;
};

/** Get the age of a launch relative to now */
export const getLaunchAge = (
	pairCreatedAt: string | null | undefined,
): string => {
	if (!pairCreatedAt) return "-";
	const created = new Date(pairCreatedAt).getTime();
	const now = Date.now();
	const diffMs = now - created;
	const diffMin = Math.floor(diffMs / 60_000);
	if (diffMin < 1) return "<1m";
	if (diffMin < 60) return `${diffMin}m`;
	const diffHr = Math.floor(diffMin / 60);
	if (diffHr < 24) return `${diffHr}h`;
	const diffDay = Math.floor(diffHr / 24);
	return `${diffDay}d`;
};
