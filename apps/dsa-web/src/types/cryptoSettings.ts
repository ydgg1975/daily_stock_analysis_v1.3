export interface CryptoSettingSchemaInfo {
	type: string;
	label: string;
	description?: string;
	default?: string;
	min?: number;
	max?: number;
	options?: string[];
	category?: string;
}

export interface CryptoSettingItem {
	key: string;
	value: string;
	rawValueExists: boolean;
	schemaInfo: CryptoSettingSchemaInfo | null;
}

export interface CryptoSettingsResponse {
	configVersion: string;
	items: CryptoSettingItem[];
	updatedAt: string | null;
}

export interface UpdateCryptoSettingsRequest {
	configVersion: string;
	items: { key: string; value: string }[];
	reloadNow: boolean;
}

export interface UpdateCryptoSettingsResponse {
	success: boolean;
	configVersion: string;
	updatedKeys: string[];
	issues: Array<{ key?: string; message?: string }>;
}
