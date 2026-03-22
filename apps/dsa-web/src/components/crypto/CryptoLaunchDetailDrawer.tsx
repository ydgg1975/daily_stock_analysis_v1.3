import { Copy, ExternalLink, X } from "lucide-react";
import type React from "react";
import { useCryptoLaunchStore } from "../../stores/cryptoLaunchStore";
import type { CryptoLaunchDetailResponse } from "../../types/crypto";
import {
	formatChainLabel,
	formatPctChange,
	formatUsd,
	getLaunchAge,
} from "../../types/crypto";
import { Drawer } from "../common/Drawer";
import { CryptoAiSummary } from "./CryptoAiSummary";
import { CryptoRiskBadge } from "./CryptoRiskBadge";

type CryptoLaunchDetailDrawerProps = {
	isOpen: boolean;
	detail: CryptoLaunchDetailResponse | null;
	isLoading: boolean;
	onClose: () => void;
};

const MetricRow: React.FC<{
	label: string;
	value: string;
	className?: string;
}> = ({ label, value, className }) => (
	<div className="flex items-center justify-between py-1.5">
		<span className="text-xs text-secondary-text">{label}</span>
		<span className={`text-xs font-mono ${className ?? "text-foreground"}`}>
			{value}
		</span>
	</div>
);

export const CryptoLaunchDetailDrawer: React.FC<
	CryptoLaunchDetailDrawerProps
> = ({ isOpen, detail, isLoading, onClose }) => {
	const launch = detail?.launch;
	const { aiSummary, isAnalyzing, analyzeError, analyzeToken, clearAiSummary } =
		useCryptoLaunchStore();
	const snapshots = detail?.snapshots ?? [];

	const handleClose = () => {
		clearAiSummary();
		onClose();
	};

	const copyAddress = (address: string) => {
		void navigator.clipboard.writeText(address);
	};

	return (
		<Drawer
			isOpen={isOpen}
			onClose={handleClose}
			title="Launch Detail"
			width="max-w-lg"
		>
			{isLoading && (
				<div className="flex items-center justify-center py-16">
					<div className="h-6 w-6 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
				</div>
			)}

			{!isLoading && !launch && (
				<div className="flex items-center justify-center py-16 text-secondary-text">
					<p className="text-sm">Launch not found</p>
				</div>
			)}

			{!isLoading && launch && (
				<div className="flex flex-col gap-5 px-1">
					{/* Header */}
					<div className="flex items-start justify-between">
						<div className="min-w-0">
							<div className="flex items-center gap-2">
								<h3 className="truncate text-lg font-semibold text-foreground">
									{launch.baseTokenSymbol || "Unknown"}
								</h3>
								<span className="rounded-full border border-border/50 px-2 py-0.5 text-xs text-secondary-text">
									{formatChainLabel(launch.chainId)}
								</span>
								{!launch.dataComplete && (
									<span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-500">
										Partial
									</span>
								)}
							</div>
							<p className="mt-0.5 text-sm text-secondary-text">
								{launch.baseTokenName || "Unnamed token"}
							</p>
						</div>
						<button
							type="button"
							onClick={handleClose}
							className="p-1 text-secondary-text hover:text-foreground"
						>
							<X className="h-4 w-4" />
						</button>
					</div>

					{/* Pair address */}
					{launch.pairAddress && (
						<div className="flex items-center gap-2 rounded-lg border border-border/30 bg-surface px-3 py-2">
							<span className="min-w-0 flex-1 truncate font-mono text-xs text-secondary-text">
								{launch.pairAddress}
							</span>
							<button
								type="button"
								onClick={() => copyAddress(launch.pairAddress)}
								className="shrink-0 p-1 text-secondary-text hover:text-foreground"
								aria-label="Copy pair address"
							>
								<Copy className="h-3.5 w-3.5" />
							</button>
						</div>
					)}

					{/* Metrics */}
					<div className="rounded-lg border border-border/30 bg-surface px-3 py-2">
						<MetricRow label="Price" value={formatUsd(launch.priceUsd)} />
						<MetricRow
							label="24h Change"
							value={formatPctChange(launch.priceChangePct24h)}
							className={
								launch.priceChangePct24h != null &&
								launch.priceChangePct24h >= 0
									? "text-emerald-500"
									: "text-red-500"
							}
						/>
						<MetricRow
							label="Liquidity"
							value={formatUsd(launch.liquidityUsd)}
						/>
						<MetricRow
							label="Volume 24h"
							value={formatUsd(launch.volumeUsd24h)}
						/>
						<MetricRow label="FDV" value={formatUsd(launch.fdvUsd)} />
						<MetricRow
							label="Market Cap"
							value={formatUsd(launch.marketCapUsd)}
						/>
						<MetricRow
							label="Txns 24h"
							value={
								launch.buys24h != null && launch.sells24h != null
									? `${launch.buys24h} buys / ${launch.sells24h} sells`
									: "-"
							}
						/>
						<MetricRow label="Age" value={getLaunchAge(launch.pairCreatedAt)} />
						<MetricRow label="Quote" value={launch.quoteTokenSymbol || "-"} />
					</div>

					<div>
						<h4 className="mb-2 text-xs font-medium text-secondary-text">
							Security
						</h4>
						<div className="rounded-lg border border-border/30 bg-surface px-3 py-3">
							<div className="flex items-start justify-between gap-3">
								<div>
									<CryptoRiskBadge
										riskScore={launch.riskScore}
										riskLevel={launch.riskLevel}
										size="md"
									/>
								</div>
							</div>

							{launch.riskScore != null ? (
								<div className="mt-3 grid gap-2 sm:grid-cols-2">
									<div className="rounded-lg border border-border/30 bg-card px-3 py-2">
										<p className="text-[11px] text-secondary-text">
											Risk Score
										</p>
										<p className="mt-1 text-sm font-medium text-foreground">
											{launch.riskScore}
										</p>
									</div>
									<div className="rounded-lg border border-border/30 bg-card px-3 py-2">
										<p className="text-[11px] text-secondary-text">
											Risk Level
										</p>
										<p className="mt-1 text-sm font-medium capitalize text-foreground">
											{launch.riskLevel || "-"}
										</p>
									</div>
								</div>
							) : (
								<p className="mt-3 text-xs text-secondary-text">
									No security scan available
								</p>
							)}
						</div>
					</div>

					{/* AI Analysis */}
					<CryptoAiSummary
						summary={aiSummary}
						isAnalyzing={isAnalyzing}
						analyzeError={analyzeError}
						onAnalyze={() => analyzeToken(launch.id)}
					/>

					{/* External links */}
					<div className="flex flex-wrap gap-2">
						{launch.dexscreenerUrl && (
							<a
								href={launch.dexscreenerUrl}
								target="_blank"
								rel="noopener noreferrer"
								className="flex items-center gap-1.5 rounded-lg border border-border/50 px-3 py-1.5 text-xs text-secondary-text transition-colors hover:border-border hover:text-foreground"
							>
								DexScreener <ExternalLink className="h-3 w-3" />
							</a>
						)}
						{launch.pairUrl && (
							<a
								href={launch.pairUrl}
								target="_blank"
								rel="noopener noreferrer"
								className="flex items-center gap-1.5 rounded-lg border border-border/50 px-3 py-1.5 text-xs text-secondary-text transition-colors hover:border-border hover:text-foreground"
							>
								GeckoTerminal <ExternalLink className="h-3 w-3" />
							</a>
						)}
						{launch.websiteUrl && (
							<a
								href={launch.websiteUrl}
								target="_blank"
								rel="noopener noreferrer"
								className="flex items-center gap-1.5 rounded-lg border border-border/50 px-3 py-1.5 text-xs text-secondary-text transition-colors hover:border-border hover:text-foreground"
							>
								Website <ExternalLink className="h-3 w-3" />
							</a>
						)}
					</div>

					{/* Snapshot History */}
					{snapshots.length > 0 && (
						<div>
							<h4 className="mb-2 text-xs font-medium text-secondary-text">
								Recent Snapshots
							</h4>
							<div className="max-h-48 overflow-auto rounded-lg border border-border/30">
								<table className="w-full text-xs">
									<thead>
										<tr className="border-b border-border/30 text-left text-secondary-text">
											<th className="px-2 py-1.5 font-medium">Time</th>
											<th className="px-2 py-1.5 text-right font-medium">
												Price
											</th>
											<th className="px-2 py-1.5 text-right font-medium">
												Liq
											</th>
											<th className="px-2 py-1.5 text-right font-medium">
												Vol
											</th>
										</tr>
									</thead>
									<tbody>
										{snapshots.map((snap) => (
											<tr key={snap.id} className="border-b border-border/20">
												<td className="whitespace-nowrap px-2 py-1 text-secondary-text">
													{snap.snapshotAt
														? new Date(snap.snapshotAt).toLocaleTimeString([], {
																hour: "2-digit",
																minute: "2-digit",
															})
														: "-"}
												</td>
												<td className="whitespace-nowrap px-2 py-1 text-right font-mono">
													{formatUsd(snap.priceUsd)}
												</td>
												<td className="whitespace-nowrap px-2 py-1 text-right font-mono">
													{formatUsd(snap.liquidityUsd)}
												</td>
												<td className="whitespace-nowrap px-2 py-1 text-right font-mono">
													{formatUsd(snap.volumeUsd24h)}
												</td>
											</tr>
										))}
									</tbody>
								</table>
							</div>
						</div>
					)}

					{/* Timestamps */}
					<div className="text-[10px] text-secondary-text/60">
						<p>
							First seen:{" "}
							{launch.firstSeenAt
								? new Date(launch.firstSeenAt).toLocaleString()
								: "-"}
						</p>
						<p>
							Last seen:{" "}
							{launch.lastSeenAt
								? new Date(launch.lastSeenAt).toLocaleString()
								: "-"}
						</p>
					</div>
				</div>
			)}
		</Drawer>
	);
};
