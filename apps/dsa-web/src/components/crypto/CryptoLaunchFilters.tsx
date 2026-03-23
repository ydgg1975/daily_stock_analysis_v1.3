import { Star } from "lucide-react";
import type React from "react";
import { useCryptoLaunchStore } from "../../stores/cryptoLaunchStore";
import type { CryptoSortMode } from "../../types/crypto";
import { formatChainLabel } from "../../types/crypto";
import { cn } from "../../utils/cn";

const KNOWN_CHAINS = [
	"ethereum",
	"bsc",
	"solana",
	"base",
	"arbitrum",
	"polygon",
	"avalanche",
	"optimism",
	"fantom",
	"celo",
];

const SORT_OPTIONS: { value: CryptoSortMode; label: string }[] = [
	{ value: "newest", label: "Newest" },
	{ value: "liquidity", label: "Liquidity" },
	{ value: "volume", label: "Volume" },
	{ value: "activity", label: "Activity" },
];

const AGE_OPTIONS = [
	{ value: 60, label: "1h" },
	{ value: 360, label: "6h" },
	{ value: 1440, label: "24h" },
	{ value: 4320, label: "3d" },
	{ value: 10080, label: "7d" },
];

type CryptoLaunchFiltersProps = {
	chains: string[];
	sort: CryptoSortMode;
	maxAgeMinutes: number;
	showWatchedOnly?: boolean;
	onChainChange: (chains: string[]) => void;
	onSortChange: (sort: CryptoSortMode) => void;
	onMaxAgeChange: (minutes: number) => void;
	onShowWatchedOnlyChange?: (value: boolean) => void;
};

export const CryptoLaunchFilters: React.FC<CryptoLaunchFiltersProps> = ({
	chains,
	sort,
	maxAgeMinutes,
	showWatchedOnly = false,
	onChainChange,
	onSortChange,
	onMaxAgeChange,
	onShowWatchedOnlyChange,
}) => {
	const { filters, setMinLiquidity, setMinVolume } = useCryptoLaunchStore();

	const toggleChain = (chain: string) => {
		if (chains.includes(chain)) {
			onChainChange(chains.filter((c) => c !== chain));
		} else {
			onChainChange([...chains, chain]);
		}
	};

	const handleMinLiquidityChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		const value = Number(e.target.value);
		setMinLiquidity(Number.isFinite(value) ? Math.max(0, value) : 0);
	};

	const handleMinVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		const value = Number(e.target.value);
		setMinVolume(Number.isFinite(value) ? Math.max(0, value) : 0);
	};

	return (
		<div className="flex flex-wrap items-center gap-3">
			{/* Chain filter pills */}
			<div className="flex flex-wrap gap-1.5">
				{KNOWN_CHAINS.map((chain) => (
					<button
						key={chain}
						type="button"
						onClick={() => toggleChain(chain)}
						className={cn(
							"rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
							chains.includes(chain)
								? "border-primary/40 bg-primary/10 text-primary"
								: "border-border/50 bg-surface text-secondary-text hover:border-border hover:text-foreground",
						)}
					>
						{formatChainLabel(chain)}
					</button>
				))}
			</div>

			{/* Divider */}
			<div className="h-6 w-px bg-border/50" />

			{/* Sort select */}
			<select
				value={sort}
				onChange={(e) => onSortChange(e.target.value as CryptoSortMode)}
				className="rounded-lg border border-border/50 bg-surface px-2.5 py-1.5 text-xs text-foreground outline-none focus:border-primary/40"
				aria-label="Sort by"
			>
				{SORT_OPTIONS.map((opt) => (
					<option key={opt.value} value={opt.value}>
						{opt.label}
					</option>
				))}
			</select>

			{/* Age filter */}
			<div className="flex gap-1">
				{AGE_OPTIONS.map((opt) => (
					<button
						key={opt.value}
						type="button"
						onClick={() => onMaxAgeChange(opt.value)}
						className={cn(
							"rounded-md px-2 py-1 text-xs font-medium transition-colors",
							maxAgeMinutes === opt.value
								? "bg-primary/10 text-primary"
								: "text-secondary-text hover:text-foreground",
						)}
					>
						{opt.label}
					</button>
				))}
			</div>

			{/* Divider */}
			<div className="h-6 w-px bg-border/50" />

			<div className="flex items-center gap-2">
				<label
					htmlFor="min-liquidity"
					className="text-xs font-medium text-secondary-text"
				>
					Min Liquidity
				</label>
				<input
					id="min-liquidity"
					type="number"
					min={0}
					step="1000"
					inputMode="numeric"
					value={filters.minLiquidityUsd || ""}
					onChange={handleMinLiquidityChange}
					placeholder="USD"
					className="w-28 rounded-lg border border-border/50 bg-surface px-2.5 py-1.5 text-xs text-foreground outline-none focus:border-primary/40"
				/>
			</div>

			<div className="flex items-center gap-2">
				<label
					htmlFor="min-volume"
					className="text-xs font-medium text-secondary-text"
				>
					Min Volume
				</label>
				<input
					id="min-volume"
					type="number"
					min={0}
					step="1000"
					inputMode="numeric"
					value={filters.minVolumeUsd || ""}
					onChange={handleMinVolumeChange}
					placeholder="USD"
					className="w-28 rounded-lg border border-border/50 bg-surface px-2.5 py-1.5 text-xs text-foreground outline-none focus:border-primary/40"
				/>
			</div>

			{/* Divider */}
			<div className="h-6 w-px bg-border/50" />

			<button
				type="button"
				onClick={() => onShowWatchedOnlyChange?.(!showWatchedOnly)}
				className={cn(
					"inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
					showWatchedOnly
						? "border-amber-400/40 bg-amber-400/10 text-amber-400"
						: "border-border/50 bg-surface text-secondary-text hover:border-border hover:text-foreground",
				)}
			>
				<Star
					className={cn("h-3.5 w-3.5", showWatchedOnly && "fill-amber-400")}
				/>
				Watched
			</button>
		</div>
	);
};
