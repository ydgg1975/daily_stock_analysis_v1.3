import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CryptoAiSummary } from "../CryptoAiSummary";

describe("CryptoAiSummary", () => {
	it("renders an Analyze with AI button when no summary exists", () => {
		const onAnalyze = vi.fn();

		render(
			<CryptoAiSummary
				summary={null}
				isAnalyzing={false}
				analyzeError={null}
				onAnalyze={onAnalyze}
			/>,
		);

		const button = screen.getByRole("button", { name: "Analyze with AI" });
		expect(button).toBeInTheDocument();

		fireEvent.click(button);
		expect(onAnalyze).toHaveBeenCalledTimes(1);
	});

	it("shows a loading state while analysis is in progress", () => {
		render(
			<CryptoAiSummary
				summary={null}
				isAnalyzing
				analyzeError={null}
				onAnalyze={vi.fn()}
			/>,
		);

		expect(screen.getByText("Analyzing with AI...")).toBeInTheDocument();
		expect(
			screen.queryByRole("button", { name: "Analyze with AI" }),
		).not.toBeInTheDocument();
	});

	it("renders the AI verdict, action, and key risks for an analyzed launch", () => {
		render(
			<CryptoAiSummary
				summary={{
					launchId: 7,
					verdict: "buy",
					confidence: 0.76,
					bullCase: "Strong buyer momentum.",
					bearCase: "Liquidity can fade quickly.",
					risks: ["Thin liquidity", "Fresh contract"],
					recommendedAction: "Wait for a retest before entering.",
					modelUsed: "gpt-test",
					promptVersion: "v1",
					analyzedAt: "2026-03-23T10:00:00Z",
					error: null,
					cached: true,
				}}
				isAnalyzing={false}
				analyzeError={null}
				onAnalyze={vi.fn()}
			/>,
		);

		expect(screen.getByText("BUY")).toBeInTheDocument();
		expect(screen.getByText("76%")).toBeInTheDocument();
		expect(
			screen.getByText("Wait for a retest before entering."),
		).toBeInTheDocument();
		expect(screen.getByText("Thin liquidity")).toBeInTheDocument();
		expect(screen.getByText("Fresh contract")).toBeInTheDocument();
		expect(screen.getByText(/Analyzed/)).toBeInTheDocument();
	});

	it("shows an error state with a retry button", () => {
		const onAnalyze = vi.fn();

		render(
			<CryptoAiSummary
				summary={null}
				isAnalyzing={false}
				analyzeError="Something went wrong"
				onAnalyze={onAnalyze}
			/>,
		);

		expect(screen.getByText("Analysis failed")).toBeInTheDocument();
		expect(screen.getByText("Something went wrong")).toBeInTheDocument();

		const retryButton = screen.getByRole("button", { name: /retry/i });
		expect(retryButton).toBeInTheDocument();

		fireEvent.click(retryButton);
		expect(onAnalyze).toHaveBeenCalledTimes(1);
	});

	it("renders a cached summary indicator when the summary is cached", () => {
		render(
			<CryptoAiSummary
				summary={{
					launchId: 7,
					verdict: "hold",
					confidence: 0.61,
					bullCase: "Volume is stabilizing.",
					bearCase: "Momentum remains unproven.",
					risks: ["Volatility"],
					recommendedAction: "Wait for confirmation.",
					modelUsed: "gpt-test",
					promptVersion: "v1",
					analyzedAt: "2026-03-23T10:00:00Z",
					error: null,
					cached: true,
				}}
				isAnalyzing={false}
				analyzeError={null}
				onAnalyze={vi.fn()}
			/>,
		);

		expect(screen.getByText("Cached")).toBeInTheDocument();
		expect(screen.getByText("HOLD")).toBeInTheDocument();
	});
});
