import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mockStoreState = {
	filters: {
		minLiquidityUsd: 25000,
		minVolumeUsd: 50000,
	},
	setMinLiquidity: vi.fn(),
	setMinVolume: vi.fn(),
};

vi.mock("../../../stores/cryptoLaunchStore", () => ({
	useCryptoLaunchStore: () => mockStoreState,
}));

import { CryptoLaunchFilters } from "../CryptoLaunchFilters";

describe("CryptoLaunchFilters", () => {
	it("renders chain control, sort dropdown, and min value inputs", () => {
		render(
			<CryptoLaunchFilters
				chains={[]}
				sort="newest"
				maxAgeMinutes={1440}
				onChainChange={vi.fn()}
				onSortChange={vi.fn()}
				onMaxAgeChange={vi.fn()}
			/>,
		);

		expect(screen.getByRole("button", { name: "Ethereum" })).toBeInTheDocument();
		expect(screen.getByLabelText("Sort by")).toBeInTheDocument();
		expect(screen.getByLabelText("Min Liquidity")).toBeInTheDocument();
		expect(screen.getByLabelText("Min Volume")).toBeInTheDocument();
	});

	it("calls store actions when min liquidity and min volume change", () => {
		render(
			<CryptoLaunchFilters
				chains={[]}
				sort="newest"
				maxAgeMinutes={1440}
				onChainChange={vi.fn()}
				onSortChange={vi.fn()}
				onMaxAgeChange={vi.fn()}
			/>,
		);

		fireEvent.change(screen.getByLabelText("Min Liquidity"), {
			target: { value: "12000" },
		});
		fireEvent.change(screen.getByLabelText("Min Volume"), {
			target: { value: "34000" },
		});

		expect(mockStoreState.setMinLiquidity).toHaveBeenCalledWith(12000);
		expect(mockStoreState.setMinVolume).toHaveBeenCalledWith(34000);
	});

	it("shows current filter values from store state", () => {
		render(
			<CryptoLaunchFilters
				chains={["ethereum"]}
				sort="liquidity"
				maxAgeMinutes={1440}
				onChainChange={vi.fn()}
				onSortChange={vi.fn()}
				onMaxAgeChange={vi.fn()}
			/>,
		);

		expect(screen.getByLabelText("Sort by")).toHaveValue("liquidity");
		expect(screen.getByLabelText("Min Liquidity")).toHaveValue(25000);
		expect(screen.getByLabelText("Min Volume")).toHaveValue(50000);
	});
});
