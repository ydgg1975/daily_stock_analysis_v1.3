import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CryptoRiskBadge } from "../CryptoRiskBadge";

describe("CryptoRiskBadge", () => {
	it("renders risk level text and rounded score for scanned launches", () => {
		render(<CryptoRiskBadge riskScore={72.4} riskLevel="high" />);

		expect(screen.getByText("72 high")).toBeInTheDocument();
	});

	it("renders N/A when no scan data exists", () => {
		render(<CryptoRiskBadge />);

		expect(screen.getByText("N/A")).toBeInTheDocument();
	});
});
