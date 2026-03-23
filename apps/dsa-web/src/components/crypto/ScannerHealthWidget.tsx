import {
	Activity,
	AlertTriangle,
	CheckCircle,
	Clock,
	XCircle,
} from "lucide-react";
import type React from "react";
import type {
	ChainTiming,
	CryptoScannerStatusResponse,
	ScanMetricRow,
} from "../../types/crypto";
import { formatChainLabel } from "../../types/crypto";
import { cn } from "../../utils/cn";

// ============ Props ============

interface ScannerHealthWidgetProps {
	status: CryptoScannerStatusResponse | null;
	className?: string;
}

// ============ Sub-components ============

const StatCell: React.FC<{
	label: string;
	value: string | number;
	accent?: "default" | "success" | "warning" | "danger";
}> = ({ label, value, accent = "default" }) => {
	const accentColor = {
		default: "text-foreground",
		success: "text-emerald-500",
		warning: "text-amber-500",
		danger: "text-red-500",
	}[accent];

	return (
		<div className="flex flex-col gap-0.5">
			<span className="text-[10px] uppercase tracking-wider text-secondary-text">
				{label}
			</span>
			<span className={cn("text-sm font-semibold tabular-nums", accentColor)}>
				{value}
			</span>
		</div>
	);
};

const ChainTimingRow: React.FC<{
	chainId: string;
	timing: ChainTiming;
}> = ({ chainId, timing }) => {
	const isOk = timing.status === "ok";
	return (
		<div className="flex items-center justify-between gap-2 text-[11px]">
			<div className="flex items-center gap-1.5">
				<span
					className={cn(
						"h-1.5 w-1.5 rounded-full",
						isOk ? "bg-emerald-500" : "bg-red-500",
					)}
				/>
				<span className="text-foreground">{formatChainLabel(chainId)}</span>
			</div>
			<div className="flex items-center gap-3 text-secondary-text">
				<span className="tabular-nums">{timing.durationMs}ms</span>
				<span className="tabular-nums">
					{timing.poolsDiscovered} pool{timing.poolsDiscovered !== 1 ? "s" : ""}
				</span>
				{(timing.retryCount ?? 0) > 0 && (
					<span className="text-amber-500">{timing.retryCount} retry</span>
				)}
			</div>
		</div>
	);
};

const ScanHistoryRow: React.FC<{ metric: ScanMetricRow }> = ({ metric }) => {
	const timeLabel = metric.finishedAt
		? new Date(metric.finishedAt).toLocaleTimeString([], {
				hour: "2-digit",
				minute: "2-digit",
				second: "2-digit",
			})
		: "-";

	return (
		<div className="flex items-center justify-between gap-2 text-[11px]">
			<div className="flex items-center gap-1.5">
				{metric.success ? (
					<CheckCircle className="h-3 w-3 text-emerald-500" />
				) : (
					<XCircle className="h-3 w-3 text-red-500" />
				)}
				<span className="tabular-nums text-secondary-text">{timeLabel}</span>
			</div>
			<div className="flex items-center gap-3 text-secondary-text tabular-nums">
				<span>{metric.durationMs}ms</span>
				<span>
					+{metric.launchesNew} / ~{metric.launchesUpdated}
				</span>
				{metric.chainsFailed > 0 && (
					<span className="text-red-500">{metric.chainsFailed} fail</span>
				)}
			</div>
		</div>
	);
};

// ============ Main Widget ============

export const ScannerHealthWidget: React.FC<ScannerHealthWidgetProps> = ({
	status,
	className,
}) => {
	if (!status) {
		return (
			<div
				className={cn(
					"rounded-xl border border-border/50 bg-card p-4",
					className,
				)}
			>
				<div className="mb-3 flex items-center gap-2">
					<Activity className="h-4 w-4 text-secondary-text" />
					<span className="text-xs font-medium text-foreground">Scanner Health</span>
				</div>
				<div className="animate-pulse space-y-3">
					<div className="grid grid-cols-4 gap-3">
						{Array.from({ length: 4 }).map((_, index) => (
							<div key={index} className="space-y-1">
								<div className="h-2 w-12 rounded bg-secondary-text/20" />
								<div className="h-4 w-10 rounded bg-secondary-text/30" />
							</div>
						))}
					</div>
					<div className="space-y-1.5">
						<div className="h-2 w-24 rounded bg-secondary-text/20" />
						<div className="h-3 w-full rounded bg-secondary-text/20" />
						<div className="h-3 w-5/6 rounded bg-secondary-text/20" />
					</div>
				</div>
			</div>
		);
	}

	const chainTimingEntries = Object.entries(status.perChainTiming ?? {});
	const recentScans = status.recentScans ?? [];
	const hasGap = status.gapDetected;

	// Derive overall health state
	const isHealthy =
		status.enabled && !hasGap && status.lastScanFailedChains.length === 0;
	const isWarning =
		status.enabled &&
		(hasGap || status.lastScanFailedChains.length > 0) &&
		status.totalScans > 0;

	// Success rate from recent scans
	const successCount = recentScans.filter((s) => s.success).length;
	const successRate =
		recentScans.length > 0
			? `${Math.round((successCount / recentScans.length) * 100)}%`
			: "-";

	return (
		<div
			className={cn(
				"rounded-xl border border-border/50 bg-card p-4",
				className,
			)}
		>
			{/* Title row */}
			<div className="mb-3 flex items-center justify-between">
				<div className="flex items-center gap-2">
					<Activity className="h-4 w-4 text-secondary-text" />
					<span className="text-xs font-medium text-foreground">
						Scanner Health
					</span>
				</div>
				<span
					className={cn(
						"inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
						isHealthy
							? "bg-emerald-500/10 text-emerald-500"
							: isWarning
								? "bg-amber-500/10 text-amber-500"
								: "bg-secondary-text/10 text-secondary-text",
					)}
				>
					{isHealthy ? "Healthy" : isWarning ? "Warning" : "Inactive"}
				</span>
			</div>

			{/* Gap alert */}
			{hasGap && (
				<div className="mb-3 flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-[11px] text-amber-500">
					<AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
					<span>
						Scan gap detected — last scan was{" "}
						{Math.round(status.gapDurationSec / 60)}m ago (expected every{" "}
						{status.refreshIntervalSec}s)
					</span>
				</div>
			)}

			{/* Stats grid */}
			<div className="mb-3 grid grid-cols-4 gap-3">
				<StatCell label="Total scans" value={status.totalScans} />
				<StatCell
					label="Last duration"
					value={`${status.lastScanDurationSec.toFixed(1)}s`}
				/>
				<StatCell
					label="Success rate"
					value={successRate}
					accent={
						successRate === "100%"
							? "success"
							: successRate === "-"
								? "default"
								: "warning"
					}
				/>
				<StatCell
					label="Failed chains"
					value={status.lastScanFailedChains.length}
					accent={status.lastScanFailedChains.length > 0 ? "danger" : "default"}
				/>
			</div>

			{/* Per-chain timing */}
			{chainTimingEntries.length > 0 && (
				<div className="mb-3">
					<div className="mb-1.5 flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-secondary-text">
						<Clock className="h-3 w-3" />
						Per-chain timing
					</div>
					<div className="flex flex-col gap-1">
						{chainTimingEntries.map(([chainId, timing]) => (
							<ChainTimingRow
								key={chainId}
								chainId={chainId}
								timing={timing as ChainTiming}
							/>
						))}
					</div>
				</div>
			)}

			{/* Recent scan history */}
			{recentScans.length > 0 && (
				<div>
					<div className="mb-1.5 text-[10px] uppercase tracking-wider text-secondary-text">
						Recent scans ({recentScans.length})
					</div>
					<div className="flex max-h-28 flex-col gap-0.5 overflow-y-auto">
						{recentScans.slice(0, 5).map((metric) => (
							<ScanHistoryRow key={metric.scanId} metric={metric} />
						))}
					</div>
				</div>
			)}
		</div>
	);
};
