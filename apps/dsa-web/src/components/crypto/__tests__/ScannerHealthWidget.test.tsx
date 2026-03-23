import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CryptoScannerStatusResponse } from "../../../types/crypto";
import { ScannerHealthWidget } from "../ScannerHealthWidget";

const statusFixture: CryptoScannerStatusResponse = {
	enabled: true,
	isScanning: false,
	refreshIntervalSec: 300,
	enabledChains: ["solana", "bsc"],
	lastScanAt: "2026-03-23T10:00:00Z",
	lastScanDurationSec: 12.3,
	lastScanChains: ["solana", "bsc"],
	lastScanFailedChains: [],
	lastScanNewLaunches: 4,
	lastScanUpdatedLaunches: 8,
	totalScans: 10,
	gapDetected: false,
	gapDurationSec: 0,
	perChainTiming: {
		solana: {
			durationMs: 300,
			poolsDiscovered: 12,
			status: "ok",
		},
		bsc: {
			durationMs: 450,
			poolsDiscovered: 8,
			status: "error",
			retryCount: 1,
		},
	},
	recentScans: [
		{
			scanId: "scan-1",
			startedAt: "2026-03-23T09:59:00Z",
			finishedAt: "2026-03-23T10:00:00Z",
			durationMs: 1200,
			chainsTotal: 2,
			chainsFailed: 0,
			launchesNew: 3,
			launchesUpdated: 5,
			perChainJson: null,
			success: true,
		},
		{
			scanId: "scan-2",
			startedAt: "2026-03-23T10:04:00Z",
			finishedAt: "2026-03-23T10:05:00Z",
			durationMs: 1500,
			chainsTotal: 2,
			chainsFailed: 1,
			launchesNew: 1,
			launchesUpdated: 2,
			perChainJson: null,
			success: false,
		},
	],
};

describe("ScannerHealthWidget", () => {
	it("shows loading skeleton when status is null", () => {
		const { container } = render(<ScannerHealthWidget status={null} />);

		expect(screen.getByText("Scanner Health")).toBeInTheDocument();
		expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
	});

	it("renders health indicators and stats with real status data", () => {
		render(<ScannerHealthWidget status={statusFixture} />);

		expect(screen.getByText("Healthy")).toBeInTheDocument();
		expect(screen.getByText("Total scans")).toBeInTheDocument();
		expect(screen.getByText("10")).toBeInTheDocument();
		expect(screen.getByText("Last duration")).toBeInTheDocument();
		expect(screen.getByText("12.3s")).toBeInTheDocument();
		expect(screen.getByText("Success rate")).toBeInTheDocument();
		expect(screen.getByText("50%")).toBeInTheDocument();
		expect(screen.getByText("Per-chain timing")).toBeInTheDocument();
		expect(screen.getByText("Solana")).toBeInTheDocument();
		expect(screen.getByText("Bsc")).toBeInTheDocument();
	});

	it("shows recent scan count and last scan time information", () => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date("2026-03-23T10:06:00Z"));

		render(<ScannerHealthWidget status={statusFixture} />);

		const expectedTime = new Date(
			statusFixture.recentScans[0].finishedAt as string,
		).toLocaleTimeString([], {
			hour: "2-digit",
			minute: "2-digit",
			second: "2-digit",
		});

		expect(screen.getByText("Recent scans (2)")).toBeInTheDocument();
		expect(screen.getByText(expectedTime)).toBeInTheDocument();
		expect(screen.getByText("+3 / ~5")).toBeInTheDocument();
		expect(screen.getByText("1 fail")).toBeInTheDocument();

		vi.useRealTimers();
	});
});
