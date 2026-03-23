import type React from "react";
import { useMemo } from "react";
import { Drawer } from "../common/Drawer";
import { useCryptoSettingsStore } from "../../stores/cryptoSettingsStore";
import type { CryptoSettingItem } from "../../types/cryptoSettings";
import { cn } from "../../utils/cn";

const CATEGORY_LABELS: Record<string, string> = {
	risk: "Risk Scoring",
	risk_scoring: "Risk Scoring",
	watchlist: "Watchlist",
	alerts: "Alerts",
	data_management: "Data Management",
	data: "Data Management",
};

const CATEGORY_ORDER = [
	"Risk Scoring",
	"Watchlist",
	"Alerts",
	"Data Management",
	"Other",
];

function getCategoryLabel(item: CryptoSettingItem): string {
	const category = item.schemaInfo?.category?.trim().toLowerCase();
	if (!category) {
		return "Other";
	}
	return CATEGORY_LABELS[category] ?? item.schemaInfo?.category?.trim() ?? "Other";
}

function parseNumberValue(value: string): string {
	if (value.trim() === "") {
		return "";
	}
	const numericValue = Number(value);
	return Number.isNaN(numericValue) ? value : String(numericValue);
}

export const CryptoSettingsPanel: React.FC = () => {
	const {
		settings,
		isLoading,
		error,
		saveError,
		isSaving,
		isOpen,
		editedValues,
		closePanel,
		setEditedValue,
		saveSettings,
		resetEdits,
	} = useCryptoSettingsStore();

	const groupedSettings = useMemo(() => {
		const groups = settings.reduce<Record<string, CryptoSettingItem[]>>((acc, item) => {
			const category = getCategoryLabel(item);
			acc[category] = [...(acc[category] ?? []), item];
			return acc;
		}, {});

		return Object.entries(groups).sort(([left], [right]) => {
			const leftIndex = CATEGORY_ORDER.indexOf(left);
			const rightIndex = CATEGORY_ORDER.indexOf(right);
			const normalizedLeft = leftIndex === -1 ? CATEGORY_ORDER.length : leftIndex;
			const normalizedRight = rightIndex === -1 ? CATEGORY_ORDER.length : rightIndex;
			return normalizedLeft - normalizedRight || left.localeCompare(right);
		});
	}, [settings]);

	const hasChanges = useMemo(
		() => settings.some((item) => (editedValues[item.key] ?? item.value) !== item.value),
		[editedValues, settings],
	);

	const handleSave = async () => {
		await saveSettings();
	};

	return (
		<Drawer isOpen={isOpen} onClose={closePanel} title="Scanner Settings" width="max-w-md">
			<div className="flex min-h-full flex-col gap-4">
				{error && (
					<div className="rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-500">
						{error}
					</div>
				)}

				{isLoading ? (
					<div className="flex items-center justify-center py-16">
						<div className="h-6 w-6 animate-spin rounded-full border-2 border-primary/20 border-t-primary" />
					</div>
				) : (
					<>
						{groupedSettings.length === 0 ? (
							<div className="rounded-xl border border-border/50 bg-surface px-4 py-5 text-sm text-secondary-text">
								No scanner settings available.
							</div>
						) : (
							<div className="space-y-6">
								{groupedSettings.map(([category, items]) => (
									<section key={category} className="space-y-3">
										<h3 className="text-xs font-medium uppercase tracking-wider text-secondary-text">
											{category}
										</h3>
										<div className="space-y-3">
											{items.map((item) => {
												const schema = item.schemaInfo;
												const value = editedValues[item.key] ?? item.value;
												const isBoolean = schema?.type === "bool";
												const isNumber = schema?.type === "int" || schema?.type === "float";
												const hasOptions = schema?.type === "str" && (schema.options?.length ?? 0) > 0;

												return (
													<div
														key={item.key}
														className="rounded-xl border border-border/50 bg-card px-4 py-3"
													>
														<div className="flex items-start justify-between gap-3">
															<div className="min-w-0 flex-1">
																<label
																	htmlFor={item.key}
																	className="text-sm font-medium text-foreground"
																>
																	{schema?.label ?? item.key}
																</label>
																{schema?.description && (
																	<p className="mt-1 text-xs leading-5 text-secondary-text">
																		{schema.description}
																	</p>
																)}
															</div>

															{isBoolean ? (
																<button
																	type="button"
																	onClick={() =>
																		setEditedValue(item.key, value === "true" ? "false" : "true")
																	}
																	className={cn(
																		"relative inline-flex h-6 w-11 shrink-0 rounded-full border border-transparent transition-colors",
																		value === "true" ? "bg-primary" : "bg-secondary-text/20",
																	)}
																	aria-pressed={value === "true"}
																>
																	<span
																		className={cn(
																			"absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform",
																			value === "true" ? "translate-x-5" : "translate-x-0.5",
																		)}
																	/>
																</button>
															) : null}
														</div>

														{!isBoolean && (
															<div className="mt-3">
																{isNumber ? (
																	<input
																		id={item.key}
																		type="number"
																		inputMode="decimal"
																		min={schema?.min}
																		max={schema?.max}
																		step={schema?.type === "int" ? 1 : "any"}
																		value={value}
																		onChange={(event) =>
																			setEditedValue(item.key, parseNumberValue(event.target.value))
																		}
																		className="w-full rounded-lg border border-border/50 bg-surface px-3 py-1.5 text-sm text-foreground outline-none transition-colors focus:border-primary/60"
																	/>
																) : hasOptions ? (
																	<select
																		id={item.key}
																		value={value}
																		onChange={(event) => setEditedValue(item.key, event.target.value)}
																		className="w-full rounded-lg border border-border/50 bg-surface px-3 py-1.5 text-sm text-foreground outline-none transition-colors focus:border-primary/60"
																	>
																		{schema?.options?.map((option) => (
																			<option key={option} value={option}>
																				{option}
																			</option>
																		))}
																	</select>
																) : (
																	<input
																		id={item.key}
																		type="text"
																		value={value}
																		onChange={(event) => setEditedValue(item.key, event.target.value)}
																		className="w-full rounded-lg border border-border/50 bg-surface px-3 py-1.5 text-sm text-foreground outline-none transition-colors focus:border-primary/60"
																	/>
																)}
															</div>
														)}
													</div>
												);
											})}
										</div>
									</section>
								))}
							</div>
						)}

						<div className="sticky bottom-0 mt-6 border-t border-border/50 bg-card/95 pt-4 backdrop-blur">
							{saveError && (
								<div className="mb-3 rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-500">
									{saveError}
								</div>
							)}
							<div className="flex items-center justify-between gap-3">
								<button
									type="button"
									onClick={() => {
										resetEdits();
										closePanel();
									}}
									className="rounded-lg border border-border/50 px-4 py-2 text-sm font-medium text-secondary-text transition-colors hover:border-border hover:text-foreground"
								>
									Cancel
								</button>
								<button
									type="button"
									onClick={() => void handleSave()}
									disabled={isSaving || !hasChanges}
									className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
								>
									{isSaving ? "Saving..." : "Save"}
								</button>
							</div>
						</div>
					</>
				)}
			</div>
		</Drawer>
	);
};
