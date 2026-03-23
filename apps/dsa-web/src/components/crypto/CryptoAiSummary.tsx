import { AlertTriangle, Bot, RefreshCw, Sparkles } from "lucide-react";
import type React from "react";
import type { CryptoAiSummary as CryptoAiSummaryType } from "../../types/crypto";

type CryptoAiSummaryProps = {
	summary: CryptoAiSummaryType | null;
	isAnalyzing: boolean;
	analyzeError: string | null;
	onAnalyze: () => void;
};

const verdictColors: Record<string, string> = {
	buy: "bg-emerald-500/15 text-emerald-500 border-emerald-500/30",
	hold: "bg-amber-500/15 text-amber-500 border-amber-500/30",
	avoid: "bg-red-500/15 text-red-500 border-red-500/30",
};

export const CryptoAiSummary: React.FC<CryptoAiSummaryProps> = ({
	summary,
	isAnalyzing,
	analyzeError,
	onAnalyze,
}) => {
	// Loading state
	if (isAnalyzing) {
		return (
			<div
				role="status"
				aria-busy="true"
				aria-label="Analyzing token with AI"
				className="rounded-lg border border-border/30 bg-surface px-3 py-4"
			>
				<div className="flex items-center gap-2">
					<div className="h-4 w-4 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
					<span className="text-xs text-secondary-text">
						Analyzing with AI...
					</span>
				</div>
				<div className="mt-3 space-y-2">
					<div className="h-3 w-3/4 animate-pulse rounded bg-border/30" />
					<div className="h-3 w-1/2 animate-pulse rounded bg-border/30" />
					<div className="h-3 w-2/3 animate-pulse rounded bg-border/30" />
				</div>
			</div>
		);
	}

	// Error state
	if (analyzeError) {
		return (
			<div
				role="alert"
				className="rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-3"
			>
				<div className="flex items-center gap-2">
					<AlertTriangle className="h-4 w-4 text-red-500" />
					<span className="text-xs text-red-500">Analysis failed</span>
				</div>
				<p className="mt-1 text-xs text-secondary-text">{analyzeError}</p>
				<button
					type="button"
					onClick={onAnalyze}
					className="mt-2 flex items-center gap-1.5 rounded-md border border-border/50 px-3 py-1 text-xs text-secondary-text transition-colors hover:border-border hover:text-foreground"
				>
					<RefreshCw className="h-3 w-3" />
					Retry
				</button>
			</div>
		);
	}

	// No summary — show analyze button
	if (!summary) {
		return (
			<div className="rounded-lg border border-border/30 bg-surface px-3 py-3">
				<button
					type="button"
					onClick={onAnalyze}
					className="flex w-full items-center justify-center gap-2 rounded-md border border-cyan/30 bg-cyan/5 px-4 py-2 text-xs font-medium text-cyan transition-colors hover:bg-cyan/10"
				>
					<Sparkles className="h-3.5 w-3.5" />
					Analyze with AI
				</button>
			</div>
		);
	}

	// Summary result
	const verdictKey = (summary.verdict ?? "").toLowerCase();
	const verdictStyle =
		verdictColors[verdictKey] ??
		"bg-secondary-text/10 text-secondary-text border-border/30";
	const confidencePct =
		summary.confidence != null ? Math.round(summary.confidence * 100) : null;

	return (
		<div className="rounded-lg border border-border/30 bg-surface px-3 py-3">
			{/* Verdict + confidence row */}
			<div className="flex items-center justify-between">
				<div className="flex items-center gap-2">
					<Bot className="h-4 w-4 text-cyan" />
					<span
						className={`rounded-md border px-2 py-0.5 text-xs font-semibold uppercase ${verdictStyle}`}
					>
						{summary.verdict?.toUpperCase() ?? "N/A"}
					</span>
					{confidencePct != null && (
						<span className="text-xs text-secondary-text">
							{confidencePct}%
						</span>
					)}
				</div>
				{summary.cached && (
					<span className="text-[10px] text-secondary-text/60">Cached</span>
				)}
			</div>

			{/* Recommended action */}
			{summary.recommendedAction && (
				<p className="mt-2 text-xs text-foreground">
					{summary.recommendedAction}
				</p>
			)}

			{/* Bull / Bear cases */}
			{(summary.bullCase || summary.bearCase) && (
				<div className="mt-3 grid gap-2 sm:grid-cols-2">
					{summary.bullCase && (
						<div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-2">
							<p className="text-[10px] font-medium text-emerald-500">Bull</p>
							<p className="mt-0.5 text-xs text-secondary-text">
								{summary.bullCase}
							</p>
						</div>
					)}
					{summary.bearCase && (
						<div className="rounded-lg border border-red-500/20 bg-red-500/5 px-2.5 py-2">
							<p className="text-[10px] font-medium text-red-500">Bear</p>
							<p className="mt-0.5 text-xs text-secondary-text">
								{summary.bearCase}
							</p>
						</div>
					)}
				</div>
			)}

			{/* Risks */}
			{summary.risks && summary.risks.length > 0 && (
				<div className="mt-3">
					<p className="text-[10px] font-medium text-secondary-text">
						Key Risks
					</p>
					<ul className="mt-1 space-y-0.5">
						{summary.risks.map((risk) => (
							<li
								key={risk}
								className="flex items-start gap-1.5 text-xs text-secondary-text"
							>
								<AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-500" />
								{risk}
							</li>
						))}
					</ul>
				</div>
			)}

			{/* Error indicator for partial results */}
			{summary.error && (
				<p className="mt-2 text-[10px] text-amber-500">
					Partial result: {summary.error}
				</p>
			)}

			{/* Metadata footer */}
			<div className="mt-3 flex items-center justify-between text-[10px] text-secondary-text/60">
				<span>
					Analyzed{" "}
					{summary.analyzedAt
						? new Date(summary.analyzedAt).toLocaleString()
						: "recently"}
				</span>
				{summary.modelUsed && <span>{summary.modelUsed}</span>}
			</div>
		</div>
	);
};
