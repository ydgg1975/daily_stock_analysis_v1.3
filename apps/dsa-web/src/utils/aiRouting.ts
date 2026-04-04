export type GatewayPresetMap = Record<string, string[]>;

export const KNOWN_GATEWAY_MODEL_PRESETS: GatewayPresetMap = {
  aihubmix: [
    'openai/gpt-4.1-mini',
    'openai/gpt-4.1-free',
    'gpt-4o-free',
    'gemini/gemini-2.5-flash',
    'gemini/gemini-3-flash-preview',
  ],
  gemini: [
    'gemini/gemini-2.5-flash',
    'gemini/gemini-3-flash-preview',
    'gemini/gemini-2.0-flash-exp',
  ],
  openai: [
    'openai/gpt-4.1-mini',
    'openai/gpt-4o-mini',
    'openai/gpt-4.1',
  ],
  anthropic: [
    'anthropic/claude-3-5-sonnet',
    'anthropic/claude-3-7-sonnet',
  ],
  deepseek: [
    'deepseek/deepseek-chat',
    'deepseek/deepseek-reasoner',
  ],
  zhipu: [
    'zhipu/glm-4-flash',
    'zhipu/glm-4-plus',
  ],
};

export const GATEWAY_READINESS_NOTES: Record<string, string> = {
  aihubmix: 'aihubmix_dynamic_pool',
  gemini: 'gemini_multi_model_single_key',
  openai: 'openai_compatible_dynamic',
  openrouter: 'openai_compatible_dynamic',
  zhipu: 'openai_compatible_dynamic',
};

export function normalizeGatewayKey(value: string): string {
  return String(value || '').trim().toLowerCase();
}

export function parseGatewayFromModel(value: string): string {
  const model = String(value || '').trim();
  if (!model || !model.includes('/')) return '';
  return normalizeGatewayKey(model.split('/', 1)[0] || '');
}

export function uniqueValues(values: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const list: string[] = [];
  values.forEach((value) => {
    const normalized = String(value || '').trim();
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    list.push(normalized);
  });
  return list;
}

export function supportsCustomModelId(gateway: string): boolean {
  const normalized = normalizeGatewayKey(gateway);
  if (!normalized) return true;
  if (normalized === 'gemini') return true;
  if (normalized === 'aihubmix') return true;
  return true;
}

export function getModelIdentityForms(model: string): string[] {
  const normalized = String(model || '').trim().toLowerCase();
  if (!normalized) return [];
  const suffix = normalized.includes('/') ? normalized.split('/').slice(1).join('/') : normalized;
  return uniqueValues([normalized, suffix]);
}

function isTrustedSavedModel(
  gateway: string,
  model: string,
  trustedOptions: string[],
): boolean {
  const normalizedGateway = normalizeGatewayKey(gateway);
  const normalizedModel = String(model || '').trim();
  if (!normalizedGateway || !normalizedModel) return false;

  const modelForms = new Set(getModelIdentityForms(normalizedModel));
  const hasTrustedIdentityMatch = trustedOptions.some((option) => (
    getModelIdentityForms(option).some((candidate) => modelForms.has(candidate))
  ));
  if (hasTrustedIdentityMatch) {
    return true;
  }

  const modelGateway = parseGatewayFromModel(normalizedModel);
  if (modelGateway && normalizedGateway !== 'aihubmix' && modelGateway !== normalizedGateway) {
    return false;
  }

  return false;
}

export function getGatewayModelOptions(
  gateway: string,
  inferredByGateway: Map<string, string[]>,
  _globalModels: string[],
  savedModels: string[],
): string[] {
  const normalized = normalizeGatewayKey(gateway);
  if (!normalized) return [];

  const declared = inferredByGateway.get(normalized) || [];
  const presets = normalized ? (KNOWN_GATEWAY_MODEL_PRESETS[normalized] || []) : [];
  const trustedBaseOptions = uniqueValues([...presets, ...declared]);
  const savedStillValid = savedModels.filter((model) => isTrustedSavedModel(
    normalized,
    model,
    trustedBaseOptions,
  ));

  return uniqueValues([...trustedBaseOptions, ...savedStillValid]);
}

export function isGatewayModelCompatible(gateway: string, model: string, options: string[]): boolean {
  const normalizedGateway = normalizeGatewayKey(gateway);
  const normalizedModel = String(model || '').trim();
  if (!normalizedGateway || !normalizedModel) return true;
  if (options.includes(normalizedModel)) return true;
  const modelForms = new Set(getModelIdentityForms(normalizedModel));
  if (options.some((option) => getModelIdentityForms(option).some((form) => modelForms.has(form)))) {
    return true;
  }
  if (normalizedGateway === 'aihubmix') return true;
  const modelGateway = parseGatewayFromModel(normalizedModel);
  if (!modelGateway) return true;
  return modelGateway === normalizedGateway;
}
