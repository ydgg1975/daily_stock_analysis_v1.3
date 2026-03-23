import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CryptoLaunchTable } from "../CryptoLaunchTable";

const mockLaunches = [
	{
		id: 1,
		chainId: "solana",
		pairAddress: "0xabc123456789",
		pairCreatedAt: "2026-03-23T00:00:00Z",
		baseTokenSymbol: "SOLX",
		baseTokenName: "SolanaX",
		liquidityUsd: 125000,
		volumeUsd24h: 89000,
		buys24h: 120,
		sells24h: 45,
		priceUsd: 1.23,
		priceChangePct24h: 12.5,
		dataComplete: true,
		riskScore: 68,
		riskLevel: "medium",
	},
	{
		id: 2,
		chainId: "ethereum",
		pairAddress: "0xdef987654321",
		pairCreatedAt: "2026-03-22T00:00:00Z",
		baseTokenSymbol: "ETHY",
		baseTokenName: "EthYield",
		liquidityUsd: 43000,
		volumeUsd24h: 22000,
		buys24h: 21,
		sells24h: 11,
		priceUsd: 0.456,
		priceChangePct24h: -4.3,
		dataComplete: true,
		riskScore: 34,
		riskLevel: "low",
	},
];

describe("CryptoLaunchTable", () => {
	it("renders table headers", () => {
		render(
			<CryptoLaunchTable launches={mockLaunches} isLoading={false} onSelect={vi.fn()} />,
		);

		expect(screen.getByText("Token")).toBeInTheDocument();
		expect(screen.getByText("Chain")).toBeInTheDocument();
		expect(screen.getByText("Risk")).toBeInTheDocument();
		expect(screen.getByText("Age")).toBeInTheDocument();
		expect(screen.getByText("Price")).toBeInTheDocument();
		expect(screen.getByText("Change")).toBeInTheDocument();
		expect(screen.getByText("Liquidity")).toBeInTheDocument();
		expect(screen.getByText("Volume 24h")).toBeInTheDocument();
		expect(screen.getByText("Txns")).toBeInTheDocument();
	});

	it("renders rows from provided data", () => {
		render(
			<CryptoLaunchTable launches={mockLaunches} isLoading={false} onSelect={vi.fn()} />,
		);

		expect(screen.getByText("SOLX")).toBeInTheDocument();
		expect(screen.getByText("EthYield")).toBeInTheDocument();
		expect(screen.getByText("120/45")).toBeInTheDocument();
		expect(screen.getByText("21/11")).toBeInTheDocument();
	});

	it("calls onSelect when a row is clicked", () => {
		const onSelect = vi.fn();
		render(
			<CryptoLaunchTable launches={mockLaunches} isLoading={false} onSelect={onSelect} />,
		);

		fireEvent.click(screen.getByRole("button", { name: /view launch SOLX/i }));

		expect(onSelect).toHaveBeenCalledWith(1);
		expect(onSelect).toHaveBeenCalledTimes(1);
	});

	it("calls onSelect on Enter and Space keyboard navigation", () => {
		const onSelect = vi.fn();
		render(
			<CryptoLaunchTable launches={mockLaunches} isLoading={false} onSelect={onSelect} />,
		);

		const row = screen.getByRole("button", { name: /view launch SOLX/i });
		fireEvent.keyDown(row, { key: "Enter" });
		fireEvent.keyDown(row, { key: " " });

		expect(onSelect).toHaveBeenCalledWith(1);
		expect(onSelect).toHaveBeenCalledTimes(2);
	});

	it("shows empty state when there is no data", () => {
		render(<CryptoLaunchTable launches={[]} isLoading={false} onSelect={vi.fn()} />);

		expect(screen.getByText("No launches found")).toBeInTheDocument();
		expect(
			screen.getByText("Try adjusting filters or wait for the next scan"),
		).toBeInTheDocument();
	});
});
