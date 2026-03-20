import { RefreshCw } from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useRef } from "react";
import { CryptoLaunchDetailDrawer } from "../components/crypto/CryptoLaunchDetailDrawer";
import { CryptoLaunchFilters } from "../components/crypto/CryptoLaunchFilters";
import { CryptoLaunchTable } from "../components/crypto/CryptoLaunchTable";
import { useCryptoLaunchStore } from "../stores/cryptoLaunchStore";
import { cn } from "../utils/cn";

const POLL_INTERVAL_MS = 60_000;

const CryptoScannerPage: React.FC = () => {
	const {
		launches,
		meta,
		isLoadingFeed,
		feedError,
		filters,
		selectedLaunch,
		isLoadingDetail,
		detailDrawerOpen,
		isRefreshing,
		scannerStatus,
		loadLaunches,
		loadMore,
		setSort,
		setChainFilter,
		setMaxAge,
		selectLaunch,
		closeDetail,
		triggerRefresh,
		loadStatus,
	} = useCryptoLaunchStore();

	const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

	// Initial load
	useEffect(() => {
		void loadLaunches();
		void loadStatus();
	}, []); // eslint-disable-line react-hooks/exhaustive-deps

	// Poll on interval + visibility change
	const pollNow = useCallback(() => {
		void loadLaunches(false);
		void loadStatus();
	}, [loadLaunches, loadStatus]);

	useEffect(() => {
		pollRef.current = setInterval(pollNow, POLL_INTERVAL_MS);
		return () => {
			if (pollRef.current) clearInterval(pollRef.current);
		};
	}, [pollNow]);

	useEffect(() => {
		const onVisibility = () => {
			if (document.visibilityState === "visible") {
				pollNow();
			}
		};
		document.addEventListener("visibilitychange", onVisibility);
		return () => document.removeEventListener("visibilitychange", onVisibility);
	}, [pollNow]);

	const lastScanLabel = scannerStatus?.lastScanAt
		? new Date(scannerStatus.lastScanAt).toLocaleTimeString([], {
				hour: "2-digit",
				minute: "2-digit",
			})
		: null;

	return (
		<div className="flex flex-col gap-5 p-4 md:p-6">
			{/* Header */}
			<div className="flex flex-wrap items-center justify-between gap-3">
				<div>
					<h1 className="text-lg font-semibold text-foreground">
						Crypto Scanner
					</h1>
					<p className="mt-0.5 text-xs text-secondary-text">
						New token launches across DEX pools
						{lastScanLabel && (
							<span className="ml-2 opacity-70">
								Last scan: {lastScanLabel}
							</span>
						)}
					</p>
				</div>

				<div className="flex items-center gap-2">
					{scannerStatus && (
						<span
							className={cn(
								"h-2 w-2 rounded-full",
								scannerStatus.enabled && scannerStatus.isScanning
									? "bg-emerald-500 shadow-[0_0_6px_theme(colors.emerald.500/40)]"
									: "bg-secondary-text/30",
							)}
							title={
								scannerStatus.enabled
									? scannerStatus.isScanning
										? "Scanner active"
										: "Scanner idle"
									: "Scanner disabled"
							}
						/>
					)}

					<button
						type="button"
						onClick={() => void triggerRefresh()}
						disabled={isRefreshing}
						className={cn(
							"flex items-center gap-1.5 rounded-lg border border-border/50 px-3 py-1.5 text-xs text-secondary-text transition-colors hover:border-border hover:text-foreground disabled:opacity-50",
						)}
					>
						<RefreshCw
							className={cn("h-3.5 w-3.5", isRefreshing && "animate-spin")}
						/>
						Refresh
					</button>
				</div>
			</div>

			{/* Filters */}
			<CryptoLaunchFilters
				chains={filters.chains}
				sort={filters.sort}
				maxAgeMinutes={filters.maxAgeMinutes}
				onChainChange={setChainFilter}
				onSortChange={setSort}
				onMaxAgeChange={setMaxAge}
			/>

			{/* Error */}
			{feedError && (
				<div className="rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-2.5 text-xs text-red-500">
					{feedError}
				</div>
			)}

			{/* Table */}
			<CryptoLaunchTable
				launches={launches}
				isLoading={isLoadingFeed}
				onSelect={(id) => void selectLaunch(id)}
				onLoadMore={() => void loadMore()}
				hasMore={!!meta?.nextCursor}
			/>

			{/* Detail drawer */}
			<CryptoLaunchDetailDrawer
				isOpen={detailDrawerOpen}
				detail={selectedLaunch}
				isLoading={isLoadingDetail}
				onClose={closeDetail}
			/>
		</div>
	);
};

export default CryptoScannerPage;
