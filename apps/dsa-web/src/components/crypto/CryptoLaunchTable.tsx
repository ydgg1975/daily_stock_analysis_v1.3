import type React from "react";
import type { CryptoLaunchRow } from "../../types/crypto";
import {
	formatChainLabel,
	formatPctChange,
	formatUsd,
	getLaunchAge,
} from "../../types/crypto";
import { cn } from "../../utils/cn";

type CryptoLaunchTableProps = {
	launches: CryptoLaunchRow[];
	isLoading: boolean;
	onSelect: (launchId: number) => void;
	onLoadMore?: () => void;
	hasMore?: boolean;
};

export const CryptoLaunchTable: React.FC<CryptoLaunchTableProps> = ({
	launches,
	isLoading,
	onSelect,
	onLoadMore,
	hasMore,
}) => {
	if (isLoading && launches.length === 0) {
		return (
			<div className="flex items-center justify-center py-16">
				<div className="h-6 w-6 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
			</div>
		);
	}

	if (!isLoading && launches.length === 0) {
		return (
			<div className="flex flex-col items-center justify-center gap-2 py-16 text-secondary-text">
				<p className="text-sm">No launches found</p>
				<p className="text-xs">
					Try adjusting filters or wait for the next scan
				</p>
			</div>
		);
	}

	return (
		<div className="overflow-x-auto">
			<table className="w-full text-sm">
				<thead>
					<tr className="border-b border-border/50 text-left text-xs text-secondary-text">
						<th className="whitespace-nowrap px-3 py-2 font-medium">Token</th>
						<th className="whitespace-nowrap px-3 py-2 font-medium">Chain</th>
						<th className="whitespace-nowrap px-3 py-2 font-medium">Age</th>
						<th className="whitespace-nowrap px-3 py-2 text-right font-medium">
							Price
						</th>
						<th className="whitespace-nowrap px-3 py-2 text-right font-medium">
							Change
						</th>
						<th className="whitespace-nowrap px-3 py-2 text-right font-medium">
							Liquidity
						</th>
						<th className="whitespace-nowrap px-3 py-2 text-right font-medium">
							Volume 24h
						</th>
						<th className="whitespace-nowrap px-3 py-2 text-right font-medium">
							Txns
						</th>
					</tr>
				</thead>
				<tbody>
					{launches.map((launch) => (
						<tr
							key={launch.id}
							onClick={() => onSelect(launch.id)}
							className={cn(
								"cursor-pointer border-b border-border/30 transition-colors hover:bg-hover",
								!launch.dataComplete && "opacity-75",
							)}
						>
							<td className="whitespace-nowrap px-3 py-2.5">
								<div className="flex items-center gap-2">
									<div className="min-w-0">
										<p className="truncate font-medium text-foreground">
											{launch.baseTokenSymbol || "Unknown"}
										</p>
										<p className="max-w-[120px] truncate text-xs text-secondary-text">
											{launch.baseTokenName ||
												launch.pairAddress.slice(0, 8) + "..."}
										</p>
									</div>
									{!launch.dataComplete && (
										<span className="shrink-0 rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-500">
											Partial
										</span>
									)}
								</div>
							</td>
							<td className="whitespace-nowrap px-3 py-2.5">
								<span className="rounded-full border border-border/50 px-2 py-0.5 text-xs text-secondary-text">
									{formatChainLabel(launch.chainId)}
								</span>
							</td>
							<td className="whitespace-nowrap px-3 py-2.5 text-xs text-secondary-text">
								{getLaunchAge(launch.pairCreatedAt)}
							</td>
							<td className="whitespace-nowrap px-3 py-2.5 text-right font-mono text-xs">
								{formatUsd(launch.priceUsd)}
							</td>
							<td
								className={cn(
									"whitespace-nowrap px-3 py-2.5 text-right font-mono text-xs",
									launch.priceChangePct24h != null &&
										launch.priceChangePct24h >= 0
										? "text-emerald-500"
										: "text-red-500",
								)}
							>
								{formatPctChange(launch.priceChangePct24h)}
							</td>
							<td className="whitespace-nowrap px-3 py-2.5 text-right font-mono text-xs">
								{formatUsd(launch.liquidityUsd)}
							</td>
							<td className="whitespace-nowrap px-3 py-2.5 text-right font-mono text-xs">
								{formatUsd(launch.volumeUsd24h)}
							</td>
							<td className="whitespace-nowrap px-3 py-2.5 text-right font-mono text-xs text-secondary-text">
								{launch.buys24h != null && launch.sells24h != null
									? `${launch.buys24h}/${launch.sells24h}`
									: "-"}
							</td>
						</tr>
					))}
				</tbody>
			</table>

			{hasMore && (
				<div className="flex justify-center py-4">
					<button
						type="button"
						onClick={onLoadMore}
						className="rounded-lg border border-border/50 px-4 py-2 text-xs text-secondary-text transition-colors hover:border-border hover:text-foreground"
					>
						Load more
					</button>
				</div>
			)}
		</div>
	);
};
