import { Activity, BarChart3, Cpu, Gauge, TrendingUp } from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useCryptoObservabilityStore } from "../../stores/cryptoObservabilityStore";
import type {
	AiCostModelRow,
	AiCostResponse,
	PromptComparisonResponse,
	PromptComparisonRow,
	ProviderMetricRow,
	ProviderMetricsResponse,
	ScanSloResponse,
} from "../../types/crypto";
import { formatChainLabel } from "../../types/crypto";
import { cn } from "../../utils/cn";

// ============ Sub-components ============

const SectionHeader: React.FC<{
	icon: React.ReactNode;
	title: string;
	subtitle?: string;
}> = ({ icon, title, subtitle }) => (
	<div className="mb-2 flex items-center gap-2">
		<span className="text-secondary-text">{icon}</span>
		<span className="text-xs font-medium text-foreground">{title}</span>
		{subtitle && (
			<span className="text-[10px] text-secondary-text">({subtitle})</span>
		)}
	</div>
);

// ---- SLO Gauge ----

const SloGauge: React.FC<{ slo: ScanSloResponse }> = ({ slo }) => {
	const pct = Math.round(slo.successRate * 100);
	const accent =
		pct >= 99
			? "text-emerald-500"
			: pct >= 95
				? "text-cyan-400"
				: pct >= 90
					? "text-amber-500"
					: "text-red-500";

	return (
		<div className="rounded-lg border border-border/50 bg-card/50 p-3">
			<SectionHeader
				icon={<Gauge className="h-3.5 w-3.5" />}
				title="Scan SLO"
				subtitle={`${slo.windowHours}h window`}
			/>
			<div className="flex items-end gap-3">
				<span className={cn("text-2xl font-bold tabular-nums", accent)}>
					{pct}%
				</span>
				<div className="flex gap-3 pb-1 text-[11px] text-secondary-text tabular-nums">
					<span>
						{slo.successes}/{slo.totalScans} ok
					</span>
					{slo.failures > 0 && (
						<span className="text-red-500">{slo.failures} fail</span>
					)}
				</div>
			</div>
			{/* Progress bar */}
			<div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-border/30">
				<div
					className={cn(
						"h-full rounded-full transition-all duration-500",
						pct >= 99
							? "bg-emerald-500"
							: pct >= 95
								? "bg-cyan-400"
								: pct >= 90
									? "bg-amber-500"
									: "bg-red-500",
					)}
					style={{ width: `${pct}%` }}
				/>
			</div>
		</div>
	);
};

// ---- Provider Metrics Table ----

const ProviderMetricsTable: React.FC<{
	metrics: ProviderMetricsResponse;
}> = ({ metrics }) => (
	<div className="rounded-lg border border-border/50 bg-card/50 p-3">
		<SectionHeader
			icon={<Activity className="h-3.5 w-3.5" />}
			title="Provider Metrics"
			subtitle="per chain"
		/>
		{metrics.chains.length === 0 ? (
			<p className="text-[11px] text-secondary-text">No data yet</p>
		) : (
			<div className="overflow-x-auto">
				<table className="w-full text-[11px]">
					<thead>
						<tr className="text-left text-secondary-text">
							<th className="pb-1 pr-3 font-medium">Chain</th>
							<th className="pb-1 pr-3 font-medium tabular-nums">Scans</th>
							<th className="pb-1 pr-3 font-medium tabular-nums">Err%</th>
							<th className="pb-1 pr-3 font-medium tabular-nums">Avg ms</th>
							<th className="pb-1 font-medium tabular-nums">Pools</th>
						</tr>
					</thead>
					<tbody>
						{metrics.chains.map((row: ProviderMetricRow) => (
							<tr key={row.chainId} className="border-t border-border/20">
								<td className="py-1 pr-3 text-foreground">
									{formatChainLabel(row.chainId)}
								</td>
								<td className="py-1 pr-3 tabular-nums text-secondary-text">
									{row.totalScans}
								</td>
								<td
									className={cn(
										"py-1 pr-3 tabular-nums",
										row.errorRate > 0.1
											? "text-red-500"
											: row.errorRate > 0
												? "text-amber-500"
												: "text-secondary-text",
									)}
								>
									{(row.errorRate * 100).toFixed(1)}%
								</td>
								<td className="py-1 pr-3 tabular-nums text-secondary-text">
									{row.avgDurationMs}
								</td>
								<td className="py-1 tabular-nums text-secondary-text">
									{row.totalPoolsDiscovered}
								</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>
		)}
	</div>
);

// ---- AI Cost Widget ----

const AiCostWidget: React.FC<{ cost: AiCostResponse }> = ({ cost }) => {
	const formatTokens = (n: number): string => {
		if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
		if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
		return String(n);
	};

	return (
		<div className="rounded-lg border border-border/50 bg-card/50 p-3">
			<SectionHeader
				icon={<Cpu className="h-3.5 w-3.5" />}
				title="AI Token Cost"
				subtitle={`${cost.windowDays}d window`}
			/>
			<div className="mb-2 grid grid-cols-3 gap-2">
				<div className="flex flex-col gap-0.5">
					<span className="text-[10px] uppercase tracking-wider text-secondary-text">
						Calls
					</span>
					<span className="text-sm font-semibold tabular-nums text-foreground">
						{cost.totalCalls}
					</span>
				</div>
				<div className="flex flex-col gap-0.5">
					<span className="text-[10px] uppercase tracking-wider text-secondary-text">
						Total tokens
					</span>
					<span className="text-sm font-semibold tabular-nums text-foreground">
						{formatTokens(cost.totalTokens)}
					</span>
				</div>
				<div className="flex flex-col gap-0.5">
					<span className="text-[10px] uppercase tracking-wider text-secondary-text">
						Prompt / Compl
					</span>
					<span className="text-xs tabular-nums text-secondary-text">
						{formatTokens(cost.promptTokens)} /{" "}
						{formatTokens(cost.completionTokens)}
					</span>
				</div>
			</div>
			{cost.byModel.length > 0 && (
				<div className="flex flex-col gap-0.5">
					{cost.byModel.map((row: AiCostModelRow) => (
						<div
							key={row.model}
							className="flex items-center justify-between text-[11px]"
						>
							<span className="truncate text-foreground">{row.model}</span>
							<span className="tabular-nums text-secondary-text">
								{row.calls} calls · {formatTokens(row.totalTokens)}
							</span>
						</div>
					))}
				</div>
			)}
		</div>
	);
};

// ---- Prompt Comparison Table ----

const PromptComparisonTable: React.FC<{
	comparison: PromptComparisonResponse;
}> = ({ comparison }) => (
	<div className="rounded-lg border border-border/50 bg-card/50 p-3">
		<SectionHeader
			icon={<TrendingUp className="h-3.5 w-3.5" />}
			title="Prompt Comparison"
		/>
		{comparison.versions.length === 0 ? (
			<p className="text-[11px] text-secondary-text">No prompt data</p>
		) : (
			<div className="overflow-x-auto">
				<table className="w-full text-[11px]">
					<thead>
						<tr className="text-left text-secondary-text">
							<th className="pb-1 pr-3 font-medium">Version</th>
							<th className="pb-1 pr-3 font-medium tabular-nums">Analyses</th>
							<th className="pb-1 pr-3 font-medium tabular-nums">Avg Conf.</th>
							<th className="pb-1 pr-3 font-medium tabular-nums">Tokens</th>
							<th className="pb-1 pr-3 font-medium tabular-nums">Avg Dur.</th>
							<th className="pb-1 font-medium">Verdicts</th>
						</tr>
					</thead>
					<tbody>
						{comparison.versions.map((row: PromptComparisonRow) => (
							<tr key={row.promptVersion} className="border-t border-border/20">
								<td className="py-1 pr-3 font-mono text-foreground">
									{row.promptVersion}
								</td>
								<td className="py-1 pr-3 tabular-nums text-secondary-text">
									{row.analyses}
								</td>
								<td className="py-1 pr-3 tabular-nums text-secondary-text">
									{row.avgConfidence != null
										? `${(row.avgConfidence * 100).toFixed(0)}%`
										: "-"}
								</td>
								<td className="py-1 pr-3 tabular-nums text-secondary-text">
									{row.totalTokens}
								</td>
								<td className="py-1 pr-3 tabular-nums text-secondary-text">
									{row.avgDurationSec != null
										? `${row.avgDurationSec.toFixed(1)}s`
										: "-"}
								</td>
								<td className="py-1">
									<div className="flex gap-1.5">
										{Object.entries(row.verdictDistribution).map(
											([verdict, count]) => (
												<span
													key={verdict}
													className={cn(
														"rounded px-1 py-0.5 text-[10px] font-medium",
														verdict === "BUY"
															? "bg-emerald-500/10 text-emerald-500"
															: verdict === "AVOID"
																? "bg-red-500/10 text-red-500"
																: "bg-amber-500/10 text-amber-500",
													)}
												>
													{verdict}: {count}
												</span>
											),
										)}
									</div>
								</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>
		)}
	</div>
);

// ============ Main Dashboard ============

const TABS = ["slo", "providers", "ai-cost", "prompts"] as const;
type Tab = (typeof TABS)[number];

const TAB_LABELS: Record<Tab, string> = {
	slo: "SLO",
	providers: "Providers",
	"ai-cost": "AI Cost",
	prompts: "Prompts",
};

interface ObservabilityDashboardProps {
	className?: string;
}

export const ObservabilityDashboard: React.FC<ObservabilityDashboardProps> = ({
	className,
}) => {
	const {
		providerMetrics,
		scanSlo,
		aiCost,
		promptComparison,
		isLoading,
		loadAll,
		pollIntervalMs,
	} = useCryptoObservabilityStore();

	const [activeTab, setActiveTab] = useState<Tab>("slo");
	const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

	// Initial load
	useEffect(() => {
		void loadAll();
	}, []); // eslint-disable-line react-hooks/exhaustive-deps

	// Dynamic polling
	const pollNow = useCallback(() => {
		void loadAll();
	}, [loadAll]);

	useEffect(() => {
		pollRef.current = setInterval(pollNow, pollIntervalMs);
		return () => {
			if (pollRef.current) clearInterval(pollRef.current);
		};
	}, [pollNow, pollIntervalMs]);

	// Visibility-based refresh
	useEffect(() => {
		const onVisibility = () => {
			if (document.visibilityState === "visible") {
				pollNow();
			}
		};
		document.addEventListener("visibilitychange", onVisibility);
		return () => document.removeEventListener("visibilitychange", onVisibility);
	}, [pollNow]);

	return (
		<div
			className={cn(
				"rounded-xl border border-border/50 bg-card p-4",
				className,
			)}
		>
			{/* Header + tabs */}
			<div className="mb-3 flex flex-wrap items-center justify-between gap-2">
				<div className="flex items-center gap-2">
					<BarChart3 className="h-4 w-4 text-secondary-text" />
					<span className="text-xs font-medium text-foreground">
						Observability
					</span>
					{isLoading && (
						<span className="h-3 w-3 animate-spin rounded-full border-2 border-cyan-500/20 border-t-cyan-500" />
					)}
				</div>
				<div className="flex gap-1">
					{TABS.map((tab) => (
						<button
							key={tab}
							type="button"
							onClick={() => setActiveTab(tab)}
							className={cn(
								"rounded-md px-2 py-1 text-[10px] font-medium transition-colors",
								activeTab === tab
									? "bg-foreground/10 text-foreground"
									: "text-secondary-text hover:text-foreground",
							)}
						>
							{TAB_LABELS[tab]}
						</button>
					))}
				</div>
			</div>

			{/* Tab content */}
			{activeTab === "slo" && scanSlo && <SloGauge slo={scanSlo} />}
			{activeTab === "slo" && !scanSlo && (
				<p className="text-[11px] text-secondary-text">
					No SLO data available yet
				</p>
			)}

			{activeTab === "providers" && providerMetrics && (
				<ProviderMetricsTable metrics={providerMetrics} />
			)}
			{activeTab === "providers" && !providerMetrics && (
				<p className="text-[11px] text-secondary-text">
					No provider data available yet
				</p>
			)}

			{activeTab === "ai-cost" && aiCost && <AiCostWidget cost={aiCost} />}
			{activeTab === "ai-cost" && !aiCost && (
				<p className="text-[11px] text-secondary-text">
					No AI cost data available yet
				</p>
			)}

			{activeTab === "prompts" && promptComparison && (
				<PromptComparisonTable comparison={promptComparison} />
			)}
			{activeTab === "prompts" && !promptComparison && (
				<p className="text-[11px] text-secondary-text">
					No prompt comparison data yet
				</p>
			)}
		</div>
	);
};
