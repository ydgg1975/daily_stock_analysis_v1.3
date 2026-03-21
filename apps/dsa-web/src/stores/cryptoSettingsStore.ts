import { create } from "zustand";
import {
	CryptoSettingsConflictError,
	CryptoSettingsValidationError,
	cryptoSettingsApi,
} from "../api/cryptoSettings";
import { toApiErrorMessage } from "../api/error";
import type { CryptoSettingItem } from "../types/cryptoSettings";

interface CryptoSettingsState {
	settings: CryptoSettingItem[];
	configVersion: string;
	isLoading: boolean;
	isSaving: boolean;
	error: string | null;
	saveError: string | null;
	isOpen: boolean;
	editedValues: Record<string, string>;
	openPanel: () => void;
	closePanel: () => void;
	loadSettings: () => Promise<void>;
	setEditedValue: (key: string, value: string) => void;
	saveSettings: () => Promise<boolean>;
	resetEdits: () => void;
}

const initialState = {
	settings: [] as CryptoSettingItem[],
	configVersion: "",
	isLoading: false,
	isSaving: false,
	error: null as string | null,
	saveError: null as string | null,
	isOpen: false,
	editedValues: {} as Record<string, string>,
};

function buildEditedValues(settings: CryptoSettingItem[]): Record<string, string> {
	return Object.fromEntries(settings.map((item) => [item.key, item.value]));
}

function getChangedItems(
	settings: CryptoSettingItem[],
	editedValues: Record<string, string>,
): Array<{ key: string; value: string }> {
	return settings
		.filter((item) => editedValues[item.key] !== item.value)
		.map((item) => ({
			key: item.key,
			value: editedValues[item.key] ?? item.value,
		}));
}

function formatValidationIssues(
	issues: Array<{ key?: string; message?: string }>,
	fallback: string,
): string {
	const messages = issues
		.map((issue) => {
			if (issue.key && issue.message) {
				return `${issue.key}: ${issue.message}`;
			}
			return issue.message || issue.key || "";
		})
		.filter(Boolean);

	return messages.length > 0 ? messages.join(" ") : fallback;
}

export const useCryptoSettingsStore = create<CryptoSettingsState>((set, get) => ({
	...initialState,

	openPanel: () => {
		set({ isOpen: true, saveError: null });
		void get().loadSettings();
	},

	closePanel: () => {
		set((state) => ({
			isOpen: false,
			saveError: null,
			error: null,
			editedValues: buildEditedValues(state.settings),
		}));
	},

	loadSettings: async () => {
		set({ isLoading: true, error: null, saveError: null });
		try {
			const response = await cryptoSettingsApi.getSettings();
			set({
				settings: response.items,
				configVersion: response.configVersion,
				editedValues: buildEditedValues(response.items),
				isLoading: false,
				error: null,
			});
		} catch (error) {
			set({
				isLoading: false,
				error: toApiErrorMessage(error, "Failed to load scanner settings"),
			});
		}
	},

	setEditedValue: (key, value) => {
		set((state) => ({
			editedValues: {
				...state.editedValues,
				[key]: value,
			},
			saveError: null,
		}));
	},

	saveSettings: async () => {
		const { settings, editedValues, configVersion } = get();
		const changedItems = getChangedItems(settings, editedValues);

		if (changedItems.length === 0) {
			set({ saveError: null });
			return true;
		}

		set({ isSaving: true, saveError: null });

		try {
			const response = await cryptoSettingsApi.updateSettings({
				configVersion,
				items: changedItems,
				reloadNow: true,
			});

			set((state) => {
				const updatedSettings = state.settings.map((item) => {
					const changedItem = changedItems.find((candidate) => candidate.key === item.key);
					return changedItem ? { ...item, value: changedItem.value } : item;
				});

				return {
					settings: updatedSettings,
					configVersion: response.configVersion,
					editedValues: buildEditedValues(updatedSettings),
					isSaving: false,
					saveError:
						response.issues.length > 0
							? formatValidationIssues(response.issues, "Settings saved with issues")
							: null,
				};
			});

			return true;
		} catch (error) {
			if (error instanceof CryptoSettingsConflictError) {
				await get().loadSettings();
				set({
					isSaving: false,
					saveError:
						error.parsedError.message
						|| "Settings were updated elsewhere. Latest values have been reloaded.",
				});
				return false;
			}

			if (error instanceof CryptoSettingsValidationError) {
				set({
					isSaving: false,
					saveError: formatValidationIssues(
						error.issues,
						error.parsedError.message || "Settings validation failed",
					),
				});
				return false;
			}

			set({
				isSaving: false,
				saveError: toApiErrorMessage(error, "Failed to save scanner settings"),
			});
			return false;
		}
	},

	resetEdits: () => {
		set((state) => ({
			editedValues: buildEditedValues(state.settings),
			saveError: null,
		}));
	},
}));
