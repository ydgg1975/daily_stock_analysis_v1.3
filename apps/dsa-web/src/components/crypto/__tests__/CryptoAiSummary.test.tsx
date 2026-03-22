import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CryptoAiSummary } from "../CryptoAiSummary";

describe("CryptoAiSummary", () => {
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
});
