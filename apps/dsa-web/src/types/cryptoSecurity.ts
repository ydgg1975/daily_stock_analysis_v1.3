export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface SecurityScanSummary {
	provider: string;
	riskScore: number;
	riskLevel: RiskLevel;
	isHoneypot: boolean;
	isMintable: boolean;
	buyTaxPct: number;
	sellTaxPct: number;
	lpLockedPct: number;
	top10HolderRatePct: number;
	autoFailReasons: string[];
}
