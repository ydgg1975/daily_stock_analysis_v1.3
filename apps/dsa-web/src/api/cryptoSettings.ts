import { createParsedApiError, getParsedApiError, type ParsedApiError } from "./error";
import apiClient from "./index";
import { toCamelCase } from "./utils";
import type {
	CryptoSettingsResponse,
	UpdateCryptoSettingsRequest,
	UpdateCryptoSettingsResponse,
} from "../types/cryptoSettings";

interface CryptoSettingsConflictResponse {
	message?: string;
	currentConfigVersion?: string;
}

interface CryptoSettingsValidationIssue {
	key?: string;
	message?: string;
}

interface CryptoSettingsValidationErrorResponse {
	message?: string;
	issues?: CryptoSettingsValidationIssue[];
}

export class CryptoSettingsValidationError extends Error {
	issues: CryptoSettingsValidationIssue[];
	parsedError: ParsedApiError;

	constructor(
		message: string,
		issues: CryptoSettingsValidationIssue[] = [],
		parsedError?: ParsedApiError,
	) {
		super(message);
		this.name = "CryptoSettingsValidationError";
		this.issues = issues;
		this.parsedError =
			parsedError ??
			createParsedApiError({
				title: "Settings validation failed",
				message,
				rawMessage: message,
				status: 400,
				category: "http_error",
			});
	}
}

export class CryptoSettingsConflictError extends Error {
	currentConfigVersion?: string;
	parsedError: ParsedApiError;

	constructor(
		message: string,
		currentConfigVersion?: string,
		parsedError?: ParsedApiError,
	) {
		super(message);
		this.name = "CryptoSettingsConflictError";
		this.currentConfigVersion = currentConfigVersion;
		this.parsedError =
			parsedError ??
			createParsedApiError({
				title: "Settings version conflict",
				message,
				rawMessage: message,
				status: 409,
				category: "http_error",
			});
	}
}

function toSnakeUpdatePayload(
	payload: UpdateCryptoSettingsRequest,
): Record<string, unknown> {
	return {
		config_version: payload.configVersion,
		items: payload.items.map((item) => ({
			key: item.key,
			value: item.value,
		})),
		reload_now: payload.reloadNow,
	};
}

export const cryptoSettingsApi = {
	async getSettings(): Promise<CryptoSettingsResponse> {
		const response = await apiClient.get<Record<string, unknown>>(
			"/api/v1/crypto/settings",
		);
		return toCamelCase<CryptoSettingsResponse>(response.data);
	},

	async updateSettings(
		request: UpdateCryptoSettingsRequest,
	): Promise<UpdateCryptoSettingsResponse> {
		try {
			const response = await apiClient.put<Record<string, unknown>>(
				"/api/v1/crypto/settings",
				toSnakeUpdatePayload(request),
			);
			return toCamelCase<UpdateCryptoSettingsResponse>(response.data);
		} catch (error: unknown) {
			const parsed = getParsedApiError(error);
			if (error && typeof error === "object" && "response" in error) {
				const status = (error as { response?: { status?: number } }).response?.status;
				const payloadData = (error as { response?: { data?: unknown } }).response?.data;

				if (status === 400) {
					const validationError =
						toCamelCase<CryptoSettingsValidationErrorResponse>(payloadData ?? {});
					throw new CryptoSettingsValidationError(
						parsed.message || validationError.message || "Settings validation failed",
						validationError.issues || [],
						parsed,
					);
				}

				if (status === 409) {
					const conflict = toCamelCase<CryptoSettingsConflictResponse>(payloadData ?? {});
					throw new CryptoSettingsConflictError(
						parsed.message || conflict.message || "Settings version conflict",
						conflict.currentConfigVersion,
						parsed,
					);
				}
			}

			throw error;
		}
	},
};
