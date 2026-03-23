import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
	AiCostResponse,
	PromptComparisonResponse,
	ProviderMetricsResponse,
	ScanSloResponse,
} from "../../../types/crypto";

// ---- Mock the store before importing the component ----

const mockStoreState = {
	providerMetrics: null as ProviderMetricsResponse | null,
	scanSlo: null as ScanSloResponse | null,
	aiCost: null as AiCostResponse | null,
	promptComparison: null as PromptComparisonResponse | null,
	isLoading: false,
	error: null as string | null,
	pollIntervalMs: 60_000,
	loadAll: vi.fn(),
	loadProviderMetrics: vi.fn(),
	loadScanSlo: vi.fn(),
	loadAiCost: vi.fn(),
	loadPromptComparison: vi.fn(),
	setPollInterval: vi.fn(),
	resetState: vi.fn(),
};

vi.mock("../../../stores/cryptoObservabilityStore", () => ({
	useCryptoObservabilityStore: () => mockStoreState,
}));

import { ObservabilityDashboard } from "../ObservabilityDashboard";

// ---- Fixtures ----

const sloFixture: ScanSloResponse = {
	windowHours: 24,
	totalScans: 100,
	successes: 97,
	failures: 3,
	successRate: 0.97,
};

const providerFixture: ProviderMetricsResponse = {
	chains: [
		{
			chainId: "solana",
			totalScans: 50,
			totalFailures: 2,
			totalDurationMs: 25000,
			totalPoolsDiscovered: 120,
			avgDurationMs: 500,
			errorRate: 0.04,
		},
		{
			chainId: "bsc",
			totalScans: 40,
			totalFailures: 0,
			totalDurationMs: 16000,
			totalPoolsDiscovered: 80,
			avgDurationMs: 400,
			errorRate: 0,
		},
	],
};

const aiCostFixture: AiCostResponse = {
	windowDays: 7,
	totalCalls: 25,
	promptTokens: 8000,
	completionTokens: 4000,
	totalTokens: 12000,
	byModel: [
		{ model: "gpt-4o-mini", calls: 20, totalTokens: 10000 },
		{ model: "gpt-4o", calls: 5, totalTokens: 2000 },
	],
};

const promptFixture: PromptComparisonResponse = {
	versions: [
		{
			promptVersion: "v1",
			analyses: 15,
			avgConfidence: 0.72,
			totalTokens: 5000,
			avgDurationSec: 3.2,
			verdictDistribution: { BUY: 5, HOLD: 7, AVOID: 3 },
		},
	],
};

// ---- Tests ----

describe("ObservabilityDashboard", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		mockStoreState.providerMetrics = null;
		mockStoreState.scanSlo = null;
		mockStoreState.aiCost = null;
		mockStoreState.promptComparison = null;
		mockStoreState.isLoading = false;
	});

	it("renders Observability header", () => {
		render(<ObservabilityDashboard />);
		expect(screen.getByText("Observability")).toBeInTheDocument();
	});

	it("calls loadAll on mount", () => {
		render(<ObservabilityDashboard />);
		expect(mockStoreState.loadAll).toHaveBeenCalledOnce();
	});

	it("shows SLO tab content when data is available", () => {
		mockStoreState.scanSlo = sloFixture;
		render(<ObservabilityDashboard />);
		// Default tab is SLO
		expect(screen.getByText("97%")).toBeInTheDocument();
		expect(screen.getByText("97/100 ok")).toBeInTheDocument();
	});

	it("shows empty SLO message when no data", () => {
		render(<ObservabilityDashboard />);
		expect(screen.getByText("No SLO data available yet")).toBeInTheDocument();
	});

	it("shows provider metrics when Providers tab is selected", () => {
		mockStoreState.providerMetrics = providerFixture;
		render(<ObservabilityDashboard />);

		fireEvent.click(screen.getByText("Providers"));

		expect(screen.getByText("Solana")).toBeInTheDocument();
		expect(screen.getByText("Bsc")).toBeInTheDocument();
	});

	it("shows AI cost data when AI Cost tab is selected", () => {
		mockStoreState.aiCost = aiCostFixture;
		render(<ObservabilityDashboard />);

		fireEvent.click(screen.getByText("AI Cost"));

		expect(screen.getByText("25")).toBeInTheDocument();
		expect(screen.getByText("12.0K")).toBeInTheDocument();
		expect(screen.getByText("gpt-4o-mini")).toBeInTheDocument();
	});

	it("shows prompt comparison when Prompts tab is selected", () => {
		mockStoreState.promptComparison = promptFixture;
		render(<ObservabilityDashboard />);

		fireEvent.click(screen.getByText("Prompts"));
		expect(screen.getByText("v1")).toBeInTheDocument();
		expect(screen.getByText("BUY: 5")).toBeInTheDocument();
		expect(screen.getByText("HOLD: 7")).toBeInTheDocument();
	});

	it("renders all 4 tab buttons", () => {
		render(<ObservabilityDashboard />);
		expect(screen.getByText("SLO")).toBeInTheDocument();
		expect(screen.getByText("Providers")).toBeInTheDocument();
		expect(screen.getByText("AI Cost")).toBeInTheDocument();
		expect(screen.getByText("Prompts")).toBeInTheDocument();
	});
});
