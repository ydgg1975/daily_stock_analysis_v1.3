import { RefreshCw, Settings } from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { CryptoLaunchDetailDrawer } from "../components/crypto/CryptoLaunchDetailDrawer";
import { CryptoLaunchFilters } from "../components/crypto/CryptoLaunchFilters";
import { CryptoLaunchTable } from "../components/crypto/CryptoLaunchTable";
import { CryptoSettingsPanel } from "../components/crypto/CryptoSettingsPanel";
import { ScannerHealthWidget } from "../components/crypto/ScannerHealthWidget";
import { useCryptoLaunchStore } from "../stores/cryptoLaunchStore";
import { useCryptoSettingsStore } from "../stores/cryptoSettingsStore";
import { cn } from "../utils/cn";

const POLL_INTERVAL_MS = 60_000;

const CryptoScannerPage: React.FC = () => {
	const {
		launches,
		meta,
		isLoadingFeed,
		feedError,
		filters,
		watchedLaunchIds,
		showWatchedOnly,
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
		toggleWatch,
		setShowWatchedOnly,
		selectLaunch,
		closeDetail,
		triggerRefresh,
		loadStatus,
	} = useCryptoLaunchStore();
	const { openPanel, isOpen: isSettingsOpen } = useCryptoSettingsStore();
	const [showHealth, setShowHealth] = useState(false);

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
						<button
							type="button"
							onClick={() => setShowHealth((v) => !v)}
							className="flex items-center gap-1.5 rounded-lg border border-border/50 px-2 py-1.5 text-xs text-secondary-text transition-colors hover:border-border hover:text-foreground"
							title="Toggle scanner health panel"
						>
							<span
								className={cn(
									"h-2 w-2 rounded-full",
									scannerStatus.enabled && scannerStatus.isScanning
										? "bg-emerald-500 shadow-[0_0_6px_theme(colors.emerald.500/40)]"
										: scannerStatus.gapDetected
											? "bg-amber-500 shadow-[0_0_6px_theme(colors.amber.500/40)]"
											: "bg-secondary-text/30",
								)}
							/>
							<span className="hidden sm:inline">Health</span>
						</button>
					)}

					<button
						type="button"
						onClick={openPanel}
						aria-expanded={isSettingsOpen}
						className="flex items-center gap-1.5 rounded-lg border border-border/50 px-3 py-1.5 text-xs text-secondary-text transition-colors hover:border-border hover:text-foreground"
					>
						<Settings className="h-3.5 w-3.5" />
						Settings
					</button>

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

			{/* Scanner health panel (collapsible) */}
			{showHealth && <ScannerHealthWidget status={scannerStatus} />}

			{/* Filters */}
			<CryptoLaunchFilters
				chains={filters.chains}
				sort={filters.sort}
				maxAgeMinutes={filters.maxAgeMinutes}
				showWatchedOnly={showWatchedOnly}
				onChainChange={setChainFilter}
				onSortChange={setSort}
				onMaxAgeChange={setMaxAge}
				onShowWatchedOnlyChange={setShowWatchedOnly}
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
				watchedIds={watchedLaunchIds}
				onSelect={(id) => void selectLaunch(id)}
				onToggleWatch={(id) => void toggleWatch(id)}
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
			<CryptoSettingsPanel />
		</div>
	);
};

export default CryptoScannerPage;
