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
};

export const GATEWAY_READINESS_NOTES: Record<string, string> = {
  aihubmix: 'aihubmix_dynamic_pool',
  gemini: 'gemini_multi_model_single_key',
  openai: 'openai_compatible_dynamic',
  openrouter: 'openai_compatible_dynamic',
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

export function getGatewayModelOptions(
  gateway: string,
  inferredByGateway: Map<string, string[]>,
  globalModels: string[],
  savedModels: string[],
): string[] {
  const normalized = normalizeGatewayKey(gateway);
  const isGatewayLikeModel = (model: string): boolean => {
    const normalizedModel = String(model || '').trim().toLowerCase();
    if (!normalized || !normalizedModel) return false;
    if (normalized === 'aihubmix') return true;
    if (normalizedModel.includes(`${normalized}/`)) return true;
    if (normalizedModel.startsWith(`${normalized}-`)) return true;
    return normalizedModel.includes(normalized);
  };
  const inferred = normalized ? (inferredByGateway.get(normalized) || []) : [];
  const presets = normalized ? (KNOWN_GATEWAY_MODEL_PRESETS[normalized] || []) : [];
  const savedScoped = savedModels.filter((model) => {
    if (!normalized) return true;
    const modelGateway = parseGatewayFromModel(model);
    if (!modelGateway) return isGatewayLikeModel(model);
    if (normalized === 'aihubmix') return true;
    return modelGateway === normalized;
  });
  const fallbackByPrefix = normalized
    ? globalModels.filter((model) => {
      const modelGateway = parseGatewayFromModel(model);
      if (!modelGateway) return false;
      if (normalized === 'aihubmix') return true;
      return modelGateway === normalized;
    })
    : globalModels;
  if (!normalized) {
    return uniqueValues([...savedScoped, ...fallbackByPrefix]);
  }
  return uniqueValues([...presets, ...inferred, ...savedScoped, ...fallbackByPrefix]);
}

export function isGatewayModelCompatible(gateway: string, model: string, options: string[]): boolean {
  const normalizedGateway = normalizeGatewayKey(gateway);
  const normalizedModel = String(model || '').trim();
  if (!normalizedGateway || !normalizedModel) return true;
  if (options.includes(normalizedModel)) return true;
  if (normalizedGateway === 'aihubmix') return true;
  const modelGateway = parseGatewayFromModel(normalizedModel);
  if (!modelGateway) return true;
  return modelGateway === normalizedGateway;
}
