import { describe, expect, it } from 'vitest';
import {
  getGatewayModelOptions,
  getModelIdentityForms,
  isGatewayModelCompatible,
} from '../aiRouting';

describe('aiRouting', () => {
  it('does not backfill stale saved Zhipu models that are not declared or curated', () => {
    const declaredByGateway = new Map<string, string[]>([
      ['zhipu', ['glm-4']],
    ]);

    const options = getGatewayModelOptions(
      'zhipu',
      declaredByGateway,
      ['zhipu/glm-5'],
      ['zhipu/glm-5'],
    );

    expect(options).toContain('glm-4');
    expect(options).toContain('zhipu/glm-4-flash');
    expect(options).not.toContain('zhipu/glm-5');
  });

  it('keeps a saved model only when it matches a trusted declaration or preset', () => {
    const declaredByGateway = new Map<string, string[]>([
      ['zhipu', ['glm-4']],
    ]);

    const options = getGatewayModelOptions(
      'zhipu',
      declaredByGateway,
      [],
      ['zhipu/glm-4', 'zhipu/glm-5'],
    );

    expect(options).toContain('zhipu/glm-4');
    expect(options).not.toContain('zhipu/glm-5');
  });

  it('returns no model options until a provider is selected', () => {
    const options = getGatewayModelOptions(
      '',
      new Map([['gemini', ['gemini/gemini-2.5-flash']]]),
      ['openai/gpt-4.1-mini'],
      ['gemini/gemini-2.5-flash'],
    );

    expect(options).toEqual([]);
  });

  it('treats bare and prefixed GLM model ids as the same identity', () => {
    expect(getModelIdentityForms('openai/glm-4')).toEqual(['openai/glm-4', 'glm-4']);
    expect(isGatewayModelCompatible('zhipu', 'openai/glm-4', ['glm-4'])).toBe(true);
  });
});
