import type React from "react";
import { cn } from "../../utils/cn";

type CryptoRiskBadgeProps = {
	riskScore?: number | null;
	riskLevel?: string | null;
	size?: "sm" | "md";
};

const riskStyles: Record<string, string> = {
	low: "bg-emerald-500/10 text-emerald-500",
	medium: "bg-amber-500/10 text-amber-500",
	high: "bg-orange-500/10 text-orange-500",
	critical: "bg-red-500/10 text-red-500",
};

export const CryptoRiskBadge: React.FC<CryptoRiskBadgeProps> = ({
	riskScore,
	riskLevel,
	size = "sm",
}) => {
	const normalizedLevel = riskLevel?.toLowerCase();
	const hasRiskData = riskScore != null && normalizedLevel;
	const displayText = hasRiskData
		? `${Math.round(riskScore)} ${normalizedLevel}`
		: "N/A";

	return (
		<span
			className={cn(
				"inline-flex items-center rounded-full font-medium",
				size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs",
				hasRiskData
					? (riskStyles[normalizedLevel] ??
							"bg-secondary-text/10 text-secondary-text")
					: "bg-secondary-text/10 text-secondary-text",
			)}
		>
			{displayText}
		</span>
	);
};
